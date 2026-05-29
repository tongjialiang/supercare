# -*- coding: utf-8 -*-
"""老年健康相关生物标志物目录（用于本地序贯分期事件序列与贝叶斯似然）。"""

from __future__ import annotations

from typing import Dict, List

# 标志物编码 -> 中文名；数值越高通常表示功能恶化或风险升高
BIOMARKER_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "npi_total": {
        "label": "NPI神经精神问卷总分",
        "direction": "higher_worse",
        "clinical_note": "BPSD 负担；分数越高精神行为症状越重",
    },
    "cognitive_inverse": {
        "label": "认知功能逆指标(100-MMSE)",
        "direction": "higher_worse",
        "clinical_note": "由 MMSE 换算，越高表示认知损害越重",
    },
    "adl_dependence": {
        "label": "日常生活依赖度(100-Barthel)",
        "direction": "higher_worse",
        "clinical_note": "Barthel 越低依赖越高，此处用逆指标便于与序贯分期事件对齐",
    },
    "moca_inverse": {
        "label": "MoCA认知逆指标(100-MoCA)",
        "direction": "higher_worse",
        "clinical_note": "蒙特利尔认知评估，与 BPSD、痴呆行为症状相关",
    },
    # 以下保留在 Excel 提取中，但不参与 BPSD 序贯分期与贝叶斯 BPSD 链
    "systolic_bp": {
        "label": "收缩压月均(mmHg)",
        "direction": "bidirectional",
        "clinical_note": "不参与 BPSD 分期（仅体征参考）",
    },
    "spo2": {
        "label": "血氧饱和度月均(%)",
        "direction": "lower_worse",
        "clinical_note": "不参与 BPSD 分期（仅体征参考）",
    },
}

# BPSD 相关序贯事件：认知 → 精神行为 → 日常生活依赖（不含血压/血氧）
SEQUENTIAL_EVENT_ORDER: List[str] = [
    "cognitive_inverse",
    "moca_inverse",
    "npi_total",
    "adl_dependence",
]

# 参与分期与 BPSD 贝叶斯更新的标志物集合
BPSD_STAGING_FEATURES: List[str] = list(SEQUENTIAL_EVENT_ORDER)

# 贝叶斯风险模型关注的结局
BAYESIAN_OUTCOMES: List[str] = [
    "bpsd_escalation",  # BPSD 升级/复发
    "fall_risk",  # 跌倒高风险
    "care_intensity",  # 需加强照护强度
]
