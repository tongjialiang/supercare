# -*- coding: utf-8 -*-
"""
BPSD 30 天升级先验：由国内外文献分层患病率与短期恶化比例推导。

假设 H：未来 30 天内 NPI 总分升高 ≥4 分或任一 NPI 分项达临床显著（≥4）。
"""

from __future__ import annotations

from typing import Any, Dict, List

# 文献校准先验 P(H|stage)，阶段 1–5 对应本地序贯分期
STAGE_BPSD_PRIORS_LITERATURE: Dict[int, float] = {
    1: 0.06,  # 早期 / MCI：CHS 任一 NPI 症状约 16–32%，短期升级率低
    2: 0.14,  # 轻度痴呆：CHS 轻度约 43% 有 NPI，λ≈0.32
    3: 0.26,  # 中度：NeDEM GDS4–5，NPI 随分期上升
    4: 0.36,  # 中重度：多域 BPSD + 进展风险 HR≈1.4（AD）
    5: 0.50,  # 重度：病程晚期 BPSD 患病率 80–90% 量级
}

STAGE_LABELS: Dict[int, str] = {
    1: "早期",
    2: "轻度进展期",
    3: "中度进展期",
    4: "中重度期",
    5: "重度/高依赖期",
}

# 各阶段推导说明（写入 JSON / Word）
STAGE_PRIOR_DERIVATION: Dict[int, str] = {
    1: "MCI/极早期：Lyketsos CHS 任一 NPI 约 16–32%；显著 NPI(≥4) 更低；月尺度升级系数 λ≈0.25 → P≈0.06",
    2: "轻度痴呆 CDR≈1：任一 NPI 约 43%；λ≈0.32 → P≈0.14",
    3: "中度 GDS4–5：NeDEM 轻–重 NPI 差约 7.6 分；激越增多；λ≈0.35 → P≈0.26",
    4: "中重度：Zhao AD 病程晚期仍常见激越/激惹；NPS 促进展 HR≈1.4；λ≈0.40 → P≈0.36",
    5: "重度 CDR≈3：AD 样本 90.8% 至少一种 BPSD；λ≈0.50 → P≈0.50",
}

PRIOR_ASSUMPTION_H = (
    "H = 未来 30 天内 BPSD 临床显著恶化（NPI 总分较基线升高 ≥4 分，"
    "或任一 NPI 分项乘积 ≥4，与 JAMA CHS 及多项试验入组标准一致）"
)

PRIOR_FORMULA_NOTE = (
    "P(H|stage) ≈ p_stage × λ_stage；p_stage 来自该期 BPSD/NPI 患病率文献，"
    "λ_stage 为月尺度症状新发或加重比例（由纵向队列启发式折算，非本机构队列 MLE）"
)

PRIOR_REFERENCES: List[Dict[str, str]] = [
    {
        "id": "1",
        "citation": "Lyketsos CG, et al. Prevalence of neuropsychiatric symptoms in dementia and MCI: "
        "results from the Cardiovascular Health Study. JAMA. 2002;288(12):1471-1478.",
        "use": "MCI/轻度/中度痴呆分期 NPI 患病率分层",
    },
    {
        "id": "2",
        "citation": "Zhao Y, et al. Neuropsychiatric or BPSD: prevalence and natural history in AD. "
        "Front Neurol. 2022;13:832199.",
        "use": "AD 病程 T0/T1 各 BPSD 患病率与激越/淡漠时序",
    },
    {
        "id": "3",
        "citation": "NeDEM Project. NPS in different stages of dementia in primary care. "
        "BMC Geriatrics. 2022;22:627.",
        "use": "GDS 分期与 NPI 强度随疾病进展升高（轻–重约 +7.6 分）",
    },
    {
        "id": "4",
        "citation": "Ismail Z, et al. NPS in early AD and risk of progression to severe dementia. "
        "Transl Psychiatry. 2021;11:325.",
        "use": "NPS 存在使 AD 进展至重度风险 HR≈1.4",
    },
    {
        "id": "5",
        "citation": "Aalten P, et al. Course of neuropsychiatric symptoms in dementia (MAASBED). "
        "Int J Geriatr Psychiatry. 2005;20(6):531-536.",
        "use": "轻度痴呆基线 NPS 随时间增加；症状持续性",
    },
    {
        "id": "6",
        "citation": "中华医学会老年医学分会. 中国阿尔茨海默病痴呆诊疗指南（2020年版）. 中华老年医学杂志.",
        "use": "数字分期 4–6 进行性认知障碍伴精神行为症状；中晚期行为症状突出",
    },
]


def get_literature_prior(stage: int) -> float:
    return STAGE_BPSD_PRIORS_LITERATURE.get(stage, 0.25)


def build_prior_evidence_payload(stage: int) -> Dict[str, Any]:
    return {
        "hypothesis": PRIOR_ASSUMPTION_H,
        "formula": PRIOR_FORMULA_NOTE,
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, ""),
        "prior_bpsd_escalation_30d": STAGE_BPSD_PRIORS_LITERATURE.get(stage, 0.25),
        "derivation": STAGE_PRIOR_DERIVATION.get(stage, ""),
        "references": PRIOR_REFERENCES,
        "source": "literature_calibrated",
    }
