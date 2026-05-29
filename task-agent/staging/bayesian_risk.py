# -*- coding: utf-8 -*-
"""
贝叶斯风险融合：文献校准分期先验 + 生物标志物 z-score 似然更新。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from staging.prior_literature import (
    build_prior_evidence_payload,
    get_literature_prior,
)

DEFAULT_BAYESIAN_JSON = Path("/srv/supercare/task-agent/output/a0_贝叶斯风险后验.json")

# 仅 BPSD 相关标志物参与 BPSD 升级的似然比更新
LIKELIHOOD_RATIOS: Dict[str, float] = {
    "npi_total": 2.4,
    "cognitive_inverse": 1.9,
    "moca_inverse": 1.7,
    "adl_dependence": 1.5,
}

ZSCORE_LR_EXPONENT_CAP = 2.5
ZSCORE_NEUTRAL_BAND = 0.08


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _odds(probability: float) -> float:
    probability = min(max(probability, 1e-6), 1 - 1e-6)
    return probability / (1 - probability)


def _probability_from_odds(odds: float) -> float:
    return odds / (1 + odds)


def _zscore_to_likelihood_ratio(z_value: float, base_likelihood_ratio: float) -> float:
    """将 z-score 连续映射为似然比：优于队列降低风险，差于队列升高风险。"""
    if abs(z_value) < ZSCORE_NEUTRAL_BAND:
        return 1.0
    exponent = min(abs(z_value), ZSCORE_LR_EXPONENT_CAP)
    if z_value > 0:
        return base_likelihood_ratio**exponent
    return base_likelihood_ratio ** (-exponent)


def _compute_cohort_zscores(
    staging_result: Dict[str, Any],
    focus: Dict[str, Any],
) -> Dict[str, float]:
    """当分期结果未带 z-score 时，由队列最新截面现场计算。"""
    features = staging_result.get("event_features", list(LIKELIHOOD_RATIOS.keys()))
    buckets: Dict[str, List[float]] = {feature: [] for feature in features}
    for case in staging_result.get("cases", []):
        latest = case.get("latest_biomarkers") or case.get("latest_snapshot", {})
        for feature in features:
            value = latest.get(feature)
            if value is not None:
                buckets[feature].append(float(value))

    zscores: Dict[str, float] = {}
    focus_latest = focus.get("latest_biomarkers", {})
    for feature in features:
        values = buckets.get(feature, [])
        observed = focus_latest.get(feature)
        if not values or observed is None:
            continue
        mean_value = float(np.mean(values))
        std_value = float(np.std(values))
        if std_value < 1e-6:
            zscores[feature] = 0.0
        else:
            zscores[feature] = round((float(observed) - mean_value) / std_value, 4)
    return zscores


def compute_bayesian_posterior(
    staging_result: Dict[str, Any],
    focus_case_id: Optional[str] = None,
    new_observations: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    focus = staging_result.get("focus_case_staging")
    if not focus and staging_result.get("cases"):
        if focus_case_id:
            focus = next((case for case in staging_result["cases"] if case.get("case_id") == focus_case_id), None)
        if not focus:
            focus = staging_result["cases"][0]

    if not focus:
        return {"error": "无序贯分期结果，无法计算贝叶斯后验"}

    stage = int(focus.get("disease_stage", focus.get("sustain_stage", 3)))
    prior_bpsd = get_literature_prior(stage)
    prior_odds = _odds(prior_bpsd)
    prior_evidence = build_prior_evidence_payload(stage)

    zscores = dict(focus.get("biomarker_zscores") or {})
    if not zscores:
        zscores = _compute_cohort_zscores(staging_result, focus)

    likelihood_updates: List[Dict[str, Any]] = []
    combined_lr = 1.0
    for feature, base_likelihood_ratio in LIKELIHOOD_RATIOS.items():
        z_value = zscores.get(feature)
        if z_value is None and new_observations and feature in new_observations:
            z_value = float(new_observations[feature])
        if z_value is None:
            continue

        feature_lr = _zscore_to_likelihood_ratio(float(z_value), base_likelihood_ratio)
        if abs(feature_lr - 1.0) < 1e-4:
            continue

        combined_lr *= feature_lr
        if z_value > 0:
            interpretation = "差于或高于队列均值，推高 BPSD 升级风险"
        elif z_value < 0:
            interpretation = "优于队列均值，降低 BPSD 升级风险"
        else:
            interpretation = "接近队列均值"
        likelihood_updates.append(
            {
                "feature": feature,
                "zscore": round(float(z_value), 4),
                "likelihood_ratio": round(feature_lr, 4),
                "interpretation": interpretation,
            }
        )

    posterior_odds = prior_odds * combined_lr
    posterior_bpsd = _probability_from_odds(posterior_odds)

    latest = focus.get("latest_biomarkers", {})
    fall_logit = -1.2 + 0.04 * float(latest.get("adl_dependence") or 0)
    fall_logit += 0.03 * float(latest.get("npi_total") or 0)
    posterior_fall = _sigmoid(fall_logit)

    care_intensity = _sigmoid(-2 + stage * 0.45 + posterior_bpsd * 2.5)

    sequential_note = ""
    if new_observations:
        sequential_note = "已融合返院后新观测进行序贯贝叶斯更新（本地运行）。"

    stage_label = focus.get("disease_stage_label", focus.get("sustain_stage_label", ""))

    return {
        "model": "贝叶斯风险融合（文献校准分期先验 + 标志物 z-score 似然）",
        "runtime": "本地计算，无外部推理服务",
        "focus_case_id": focus.get("case_id"),
        "disease_stage_prior": stage,
        "prior_evidence": prior_evidence,
        "biomarker_zscores_used": zscores,
        "priors": {
            "bpsd_escalation_30d": round(prior_bpsd, 4),
            "stage_label": stage_label,
            "source": "literature_calibrated",
        },
        "likelihood_updates": likelihood_updates,
        "combined_likelihood_ratio": round(combined_lr, 4),
        "posteriors": {
            "bpsd_escalation_30d": round(posterior_bpsd, 4),
            "fall_high_risk_30d": round(posterior_fall, 4),
            "care_intensity_escalation": round(care_intensity, 4),
        },
        "calculation_steps": {
            "prior_odds": round(prior_odds, 4),
            "posterior_odds": round(posterior_odds, 4),
            "formula": "odds(H|D) = odds(H) × ∏ LR_i；P(H|D) = odds / (1+odds)",
        },
        "credible_interval_note": "先验由文献分层患病率×月尺度恶化系数推导；后验融合队列 z-score",
        "sequential_update": sequential_note,
        "decision_thresholds": {
            "gp_consult_recommended": posterior_bpsd >= 0.35,
            "nurse_weekly_npi": posterior_bpsd >= 0.25,
            "caregiver_enhanced_monitoring": posterior_bpsd >= 0.20,
        },
        "gp_actions": _bayesian_gp_actions(posterior_bpsd, posterior_fall, stage),
    }


def _bayesian_gp_actions(posterior_bpsd: float, posterior_fall: float, stage: int) -> List[str]:
    actions: List[str] = []
    if posterior_bpsd >= 0.35:
        actions.append("建议在 D7 前安排精神科/GP 会诊复核，并收紧 NPI 监测频次至每周 2 次")
    elif posterior_bpsd >= 0.25:
        actions.append("维持非药物干预，设置 NPI 较基线升高 ≥4 分的升级阈值")
    else:
        actions.append("维持当前 BPSD 预防方案，按双周复评")
    if posterior_fall >= 0.3 or stage >= 4:
        actions.append("强化夜间如厕陪护与洗澡防滑流程（与功能衰退亚型一致）")
    if stage <= 2 and posterior_bpsd < 0.2:
        actions.append("可进入稳定期管理路径，重点巩固认知活动与慢病指标")
    return actions


def save_bayesian_result(payload: Dict[str, Any], output_path: Path = DEFAULT_BAYESIAN_JSON) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
