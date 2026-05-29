# -*- coding: utf-8 -*-
"""
经典 SuStaIn 风格：每个生物标志物对应一个序贯事件异常模型 + MCMC 推断阶段/亚型。

- 亚型：标志物异常出现的顺序不同；
- 每个事件：该标志物在分期轴上的起始位置（onset）与 logistic 异常模型；
- 分期 s：全体标志物共同处于轨迹位置 1..S；
- 观测：各标志物水平由「是否已越过该事件 onset」决定期望水平。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from staging.biomarker_catalog import BPSD_STAGING_FEATURES, SEQUENTIAL_EVENT_ORDER
from staging.sequential_staging_model import (
    DEFAULT_STAGING_JSON,
    STAGE_COUNT,
    SUBTYPE_EVENT_PERMUTATIONS,
    _stage_label,
    _zscore_matrix,
)

DEFAULT_MCMC_JSON = Path("/srv/supercare/task-agent/output/a0_SuStaIn_MCMC分期结果.json")

# MCMC 配置（队列较小时控制迭代量）
MCMC_ITERATIONS = 8000
MCMC_BURN_IN = 2000
MCMC_THIN = 5
SIGMOID_WIDTH = 0.65


@dataclass
class EventModelParams:
    """单个生物标志物（序贯事件）的异常进展模型参数。"""

    feature: str
    baseline: float
    abnormal_level: float
    onset_stage: float
    width: float

    def expected_level(self, stage: float) -> float:
        probability = 1.0 / (1.0 + np.exp(-(stage - self.onset_stage) / max(self.width, 0.1)))
        return self.baseline + probability * (self.abnormal_level - self.baseline)


def _build_event_models_for_subtype(
    event_order: List[str],
    snapshots: List[Dict[str, Any]],
    features: List[str],
) -> Dict[str, EventModelParams]:
    """按亚型事件顺序，为每个标志物标定 onset 与 baseline/abnormal 水平。"""
    feature_index = {name: index for index, name in enumerate(features)}
    matrix = []
    for snap in snapshots:
        row = [float(snap.get(feature, np.nan)) for feature in features]
        matrix.append(row)
    data = np.array(matrix, dtype=float)
    models: Dict[str, EventModelParams] = {}
    total_events = len([event for event in event_order if event in feature_index])
    for event_index, event in enumerate(event_order):
        if event not in feature_index:
            continue
        column = data[:, feature_index[event]]
        valid = column[~np.isnan(column)]
        if valid.size == 0:
            continue
        baseline = float(np.nanpercentile(column, 25))
        abnormal = float(np.nanpercentile(column, 75))
        if not np.isfinite(baseline):
            baseline = float(np.nanmean(column))
        if not np.isfinite(abnormal):
            abnormal = baseline + 1.0
        if abs(abnormal - baseline) < 1e-6:
            abnormal = baseline + 1.0
        # 事件越靠后，onset 分期越晚（SuStaIn 序贯）
        onset = 1.2 + (event_index + 0.5) * (STAGE_COUNT - 1.2) / max(total_events, 1)
        models[event] = EventModelParams(
            feature=event,
            baseline=baseline,
            abnormal_level=abnormal,
            onset_stage=onset,
            width=SIGMOID_WIDTH,
        )
    return models


def _log_likelihood(
    stage: int,
    subtype: int,
    values: Dict[str, float],
    features: List[str],
    snapshots: List[Dict[str, Any]],
) -> float:
    event_order = SUBTYPE_EVENT_PERMUTATIONS[subtype - 1]
    models = _build_event_models_for_subtype(event_order, snapshots, features)
    log_likelihood = 0.0
    for feature in features:
        if feature not in values or values[feature] is None:
            continue
        if feature not in models:
            continue
        observed = float(values[feature])
        expected = models[feature].expected_level(float(stage))
        sigma = max(np.std([float(s.get(feature, observed)) for s in snapshots if s.get(feature) is not None]), 1.0)
        residual = (observed - expected) / sigma
        log_likelihood -= 0.5 * residual * residual
    return log_likelihood


def _mcmc_infer_cohort(
    snapshots: List[Dict[str, Any]],
    case_ids: List[str],
    features: List[str],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """Metropolis-Hastings：为每位老人推断亚型与共同分期。"""
    n_cases = len(case_ids)
    subtype_states = np.random.randint(1, len(SUBTYPE_EVENT_PERMUTATIONS) + 1, size=n_cases)
    stage_states = np.random.randint(1, STAGE_COUNT + 1, size=n_cases)

    value_map = {
        case_ids[index]: {feature: snapshots[index].get(feature) for feature in features}
        for index in range(n_cases)
    }

    accepted = 0
    proposals = 0
    trace_stages: List[np.ndarray] = []
    trace_subtypes: List[np.ndarray] = []

    for iteration in range(MCMC_ITERATIONS):
        for index in range(n_cases):
            proposals += 1
            current_subtype = int(subtype_states[index])
            current_stage = int(stage_states[index])
            propose_subtype = current_subtype
            propose_stage = current_stage
            if np.random.rand() < 0.35:
                propose_subtype = np.random.randint(1, len(SUBTYPE_EVENT_PERMUTATIONS) + 1)
            if np.random.rand() < 0.5:
                propose_stage = int(np.clip(current_stage + np.random.choice([-1, 0, 1]), 1, STAGE_COUNT))

            values = value_map[case_ids[index]]
            log_alpha = _log_likelihood(propose_stage, propose_subtype, values, features, snapshots) - _log_likelihood(
                current_stage, current_subtype, values, features, snapshots
            )
            if np.log(np.random.rand()) < log_alpha:
                subtype_states[index] = propose_subtype
                stage_states[index] = propose_stage
                accepted += 1

        if iteration >= MCMC_BURN_IN and iteration % MCMC_THIN == 0:
            trace_stages.append(stage_states.copy())
            trace_subtypes.append(subtype_states.copy())

    acceptance_rate = accepted / max(proposals, 1)
    results: Dict[str, Dict[str, Any]] = {}
    for index, case_id in enumerate(case_ids):
        if trace_stages:
            stage_mode = int(np.round(np.median([int(trace[index]) for trace in trace_stages])))
            subtype_mode = int(np.round(np.median([int(trace[index]) for trace in trace_subtypes])))
        else:
            stage_mode = int(stage_states[index])
            subtype_mode = int(subtype_states[index])
        stage_mode = int(np.clip(stage_mode, 1, STAGE_COUNT))
        subtype_mode = int(np.clip(subtype_mode, 1, len(SUBTYPE_EVENT_PERMUTATIONS)))
        event_order = SUBTYPE_EVENT_PERMUTATIONS[subtype_mode - 1]
        models = _build_event_models_for_subtype(event_order, snapshots, features)
        events_reached = [
            event
            for event in event_order
            if event in models and float(stage_mode) >= models[event].onset_stage - 0.3
        ]
        results[case_id] = {
            "disease_subtype": subtype_mode,
            "disease_stage": stage_mode,
            "disease_stage_label": _stage_label(stage_mode),
            "event_order": event_order,
            "events_reached": events_reached,
            "events_pending": [event for event in event_order if event in models and event not in events_reached],
            "sequential_event_count": len(events_reached),
            "sequential_event_total": len([event for event in event_order if event in models]),
        }

    diagnostics = {
        "iterations": MCMC_ITERATIONS,
        "burn_in": MCMC_BURN_IN,
        "acceptance_rate": round(acceptance_rate, 4),
        "method": "Metropolis-Hastings MCMC",
    }
    return results, diagnostics


def build_progression_curves(
    subtype: int,
    snapshots: List[Dict[str, Any]],
    features: List[str],
    mcmc_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    构建 n 条疾病进展曲线数据：横轴=分期 1..S，纵轴=标志物水平。
    每条曲线 = 一个标志物；点为队列在该分期的经验均值，线为事件模型拟合值。
    """
    event_order = SUBTYPE_EVENT_PERMUTATIONS[subtype - 1]
    models = _build_event_models_for_subtype(event_order, snapshots, features)

    # 按 MCMC 分期分桶
    stage_buckets: Dict[int, List[Dict[str, float]]] = {stage: [] for stage in range(1, STAGE_COUNT + 1)}
    for index, snap in enumerate(snapshots):
        case_id = snap.get("case_id", "")
        if case_id not in mcmc_results:
            continue
        stage = int(mcmc_results[case_id]["disease_stage"])
        stage_buckets[stage].append({feature: snap.get(feature) for feature in features})

    curves: List[Dict[str, Any]] = []
    stages_axis = list(range(1, STAGE_COUNT + 1))
    for feature in event_order:
        if feature not in models:
            continue
        model = models[feature]
        fitted_levels = [round(model.expected_level(float(stage)), 4) for stage in stages_axis]
        empirical_levels = []
        for stage in stages_axis:
            bucket = stage_buckets[stage]
            values = [float(row[feature]) for row in bucket if row.get(feature) is not None]
            empirical_levels.append(round(float(np.mean(values)), 4) if values else None)
        curves.append(
            {
                "feature": feature,
                "stages": stages_axis,
                "fitted_levels": fitted_levels,
                "empirical_means": empirical_levels,
                "event_model": {
                    "baseline": model.baseline,
                    "abnormal_level": model.abnormal_level,
                    "onset_stage": model.onset_stage,
                    "width": model.width,
                },
            }
        )

    return {
        "subtype": subtype,
        "event_order": event_order,
        "curves": curves,
        "axis_x": "疾病分期 (1-5)",
        "axis_y": "生物标志物水平（原始单位）",
    }


def run_sustain_mcmc_staging(
    cohort_payload: Dict[str, Any],
    focus_case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """SuStaIn 风格 MCMC 分期 + 进展曲线。"""
    snapshots = [case.get("latest_snapshot", {}) for case in cohort_payload.get("cases", [])]
    snapshots = [snap for snap in snapshots if snap.get("case_id")]
    candidate_order = [event for event in SEQUENTIAL_EVENT_ORDER if event in BPSD_STAGING_FEATURES]
    features = [event for event in candidate_order if any(snap.get(event) is not None for snap in snapshots)]
    if not features:
        return {"error": "无可用 BPSD 标志物"}

    z_matrix, case_ids = _zscore_matrix(snapshots, features)
    case_id_to_index = {case_id: index for index, case_id in enumerate(case_ids)}

    mcmc_results, diagnostics = _mcmc_infer_cohort(snapshots, case_ids, features)

    case_outputs: List[Dict[str, Any]] = []
    for snap in snapshots:
        case_id = snap.get("case_id", "")
        row_index = case_id_to_index.get(case_id, 0)
        biomarker_zscores = {
            features[column_index]: round(float(z_matrix[row_index, column_index]), 4)
            for column_index in range(len(features))
        }
        inferred = mcmc_results.get(case_id, {})
        event_order = inferred.get("event_order", features)
        models = _build_event_models_for_subtype(event_order, snapshots, features)
        event_status = {
            event: {
                "triggered": event in inferred.get("events_reached", []),
                "expected_at_patient_stage": round(
                    float(models[event].expected_level(float(inferred.get("disease_stage", 3)))),
                    4,
                ),
                "onset_stage": models[event].onset_stage,
            }
            for event in models
        }
        case_outputs.append(
            {
                "case_id": case_id,
                "folder_name": snap.get("folder_name", ""),
                "is_focus_case": case_id == focus_case_id,
                "latest_biomarkers": {key: snap.get(key) for key in features},
                "biomarker_zscores": biomarker_zscores,
                **inferred,
                "event_status": event_status,
                "staging_inference": "每标志物一个序贯事件异常模型，MCMC 推断共同分期与亚型",
            }
        )

    focus = next((item for item in case_outputs if item.get("is_focus_case")), case_outputs[0] if case_outputs else None)
    focus_subtype = int(focus.get("disease_subtype", 1)) if focus else 1
    progression_curves = build_progression_curves(focus_subtype, snapshots, features, mcmc_results)

    return {
        "model": "本地序贯事件异常模型 + Metropolis-Hastings MCMC（SuperCare 实现）",
        "staging_paradigm": "每个生物标志物对应一个序贯事件异常模型；横轴分期、纵轴水平的 n 条进展曲线",
        "event_features": features,
        "stage_count": STAGE_COUNT,
        "subtype_count": len(SUBTYPE_EVENT_PERMUTATIONS),
        "cohort_size": len(case_outputs),
        "focus_case_id": focus_case_id,
        "focus_case_staging": focus,
        "cases": case_outputs,
        "mcmc_diagnostics": diagnostics,
        "progression_curves": progression_curves,
        "gp_care_implications": _gp_implications_from_focus(focus),
    }


def _gp_implications_from_focus(focus: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not focus:
        return {}
    stage = int(focus.get("disease_stage", 3))
    return {
        "stage": stage,
        "subtype": focus.get("disease_subtype"),
        "monitoring_intensity": "加强" if stage >= 4 else "标准",
        "bpsd_prevention_priority": "高" if stage >= 4 else "中",
    }


def _json_safe(value: Any) -> Any:
    """将 NaN/Inf 转为 null，避免 JSON 非法。"""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    return value


def save_mcmc_staging_result(payload: Dict[str, Any], output_path: Path = DEFAULT_STAGING_JSON) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def save_progression_curves_json(payload: Dict[str, Any], output_path: Path = DEFAULT_MCMC_JSON) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
