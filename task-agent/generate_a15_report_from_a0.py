#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据 A0 JSON 生成 A15 分期报告 Markdown（与 MCMC 结果一致，不调用 LLM）。"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
STAGING_JSON = OUTPUT_DIR / "a0_序贯疾病分期结果.json"
BAYESIAN_JSON = OUTPUT_DIR / "a0_贝叶斯风险后验.json"
REPORT_MD = OUTPUT_DIR / "a15_老年健康序贯分期与贝叶斯风险报告.md"

BIOMARKER_LABELS = {
    "cognitive_inverse": "MMSE 认知逆指标",
    "moca_inverse": "MoCA 认知逆指标",
    "npi_total": "NPI 总分",
    "adl_dependence": "Barthel/ADL 依赖度",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_report_markdown(staging: dict, bayesian: dict) -> str:
    focus = staging.get("focus_case_staging", {})
    folder = focus.get("folder_name", "病例")
    case_id = focus.get("case_id", "")
    stage = focus.get("disease_stage")
    stage_label = focus.get("disease_stage_label", "")
    subtype = focus.get("disease_subtype")
    event_order = focus.get("event_order", [])
    reached = focus.get("events_reached", [])
    pending = focus.get("events_pending", [])
    biomarkers = focus.get("latest_biomarkers", {})
    curves = staging.get("progression_curves", {})
    mcmc = staging.get("mcmc_diagnostics", {})

    prior = float(bayesian.get("priors", {}).get("bpsd_escalation_30d", 0))
    posterior = float(bayesian.get("posteriors", {}).get("bpsd_escalation_30d", 0))
    combined_lr = bayesian.get("combined_likelihood_ratio", 1.0)
    prior_evidence = bayesian.get("prior_evidence", {})
    calc_steps = bayesian.get("calculation_steps", {})
    updates = bayesian.get("likelihood_updates", [])
    thresholds = bayesian.get("decision_thresholds", {})
    gp_actions = bayesian.get("gp_actions", [])

    lines = [
        "# 老年健康序贯分期与贝叶斯风险报告",
        "",
        f"**病例**：{folder}（case_id: {case_id}）  ",
        "**依据**：本地序贯事件异常模型 + Metropolis-Hastings MCMC + 贝叶斯风险融合（A0 本地流水线）  ",
        f"**MCMC 接受率**：{mcmc.get('acceptance_rate', '—')}  ",
        "",
        "---",
        "",
        "## 一、生物标志物摘要（BPSD 相关，最新截面）",
        "",
        "| 标志物 | 实测值 | 说明 |",
        "|--------|--------|------|",
    ]
    for feature in staging.get("event_features", []):
        value = biomarkers.get(feature)
        label = BIOMARKER_LABELS.get(feature, feature)
        if value is None:
            lines.append(f"| {label} | — | 无数据 |")
        else:
            lines.append(f"| {label} | {value} | 参与序贯事件模型 |")

    lines.extend(
        [
            "",
            "> 收缩压/血氧不参与分期，仅用于贝叶斯或体征监测。",
            "",
            "## 二、MCMC 疾病阶段与亚型",
            "",
            f"- **整体疾病阶段**：{stage}（{stage_label}）",
            f"- **亚型**：{subtype}（事件顺序：{' → '.join(BIOMARKER_LABELS.get(e, e) for e in event_order)}）",
            f"- **已触发序贯事件**：{', '.join(BIOMARKER_LABELS.get(e, e) for e in reached) or '无'}",
            f"- **未触发事件**：{', '.join(BIOMARKER_LABELS.get(e, e) for e in pending) or '无'}",
            "",
            "## 三、疾病进展曲线（横轴=分期，纵轴=水平）",
            "",
            "每个 BPSD 标志物对应一条 logistic 拟合曲线；详见配图 `a0_疾病进展曲线_陈女士.png`。",
            "",
        ]
    )
    for curve in curves.get("curves", []):
        feature = curve.get("feature", "")
        label = BIOMARKER_LABELS.get(feature, feature)
        onset = curve.get("event_model", {}).get("onset_stage")
        fitted = curve.get("fitted_levels", [])
        lines.append(f"- **{label}**：onset≈{onset}；分期 1–5 拟合水平 {fitted}")

    lines.extend(
        [
            "",
            "## 四、贝叶斯后验与决策阈值（文献先验）",
            "",
            f"- **假设 H**：{prior_evidence.get('hypothesis', '30天内 BPSD 临床显著恶化')}",
            f"- **文献先验 P(H)**：{prior:.1%}（阶段 {bayesian.get('disease_stage_prior')}；{prior_evidence.get('derivation', '')}）",
            f"- **先验 odds**：{calc_steps.get('prior_odds', '—')}",
            f"- **合并似然比 ∏LR**：{combined_lr}",
            f"- **后验 odds**：{calc_steps.get('posterior_odds', '—')} → **后验 P(H|D)**：{posterior:.1%}",
            "",
            "**似然更新项**：",
        ]
    )
    for reference in prior_evidence.get("references", [])[:3]:
        lines.append(f"- 文献[{reference.get('id')}]：{reference.get('use', '')}")
    for item in updates:
        lines.append(
            f"- {BIOMARKER_LABELS.get(item.get('feature'), item.get('feature'))}："
            f"z={item.get('zscore')} → LR={item.get('likelihood_ratio')}"
        )

    lines.extend(["", "**决策阈值**：", ""])
    for key, value in (thresholds or {}).items():
        lines.append(f"- {key}：{value}")

    lines.extend(["", "## 五、超级 GP 分层照护建议", ""])
    gp_impl = staging.get("gp_care_implications", {})
    if gp_impl:
        lines.append(f"- 监测强度：{gp_impl.get('monitoring_intensity', '标准')}")
        lines.append(f"- BPSD 预防优先级：{gp_impl.get('bpsd_prevention_priority', '中')}")

    for action in gp_actions or []:
        lines.append(f"- {action}")

    lines.extend(
        [
            "",
            "## 六、与 A3 / A6 / A8 协同",
            "",
            "- **A3**：会诊阈值与分层方案引用本报告后验与阶段；",
            "- **A8**：BPSD 升级监测对齐后验概率与序贯事件触发状态；",
            "- **A6**：返院任务包按阶段调整非药物干预与评估频次。",
            "",
            "---",
            "",
            "*本报告由 generate_a15_report_from_a0.py 自 A0 JSON 自动生成，与 run_staging_pipeline 结果一致。*",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    staging = _load(STAGING_JSON)
    bayesian = _load(BAYESIAN_JSON)
    REPORT_MD.write_text(build_report_markdown(staging, bayesian), encoding="utf-8")
    print(f"已写入: {REPORT_MD}")

    from common_utils import build_pdf_lines, create_pdf_report

    pdf_path = OUTPUT_DIR / "a15_老年健康序贯分期与贝叶斯风险报告.pdf"
    body = REPORT_MD.read_text(encoding="utf-8")
    create_pdf_report("老年健康序贯分期与贝叶斯风险报告", build_pdf_lines(body), pdf_path)
    print(f"已写入: {pdf_path}")


if __name__ == "__main__":
    main()
