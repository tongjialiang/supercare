# -*- coding: utf-8 -*-
"""
本地序贯疾病分期模型（SuperCare 自研，本地运行）。

核心思想（与「逐标志物打分再汇总」不同）：
- 全体 BPSD 相关标志物在同一条 **序贯事件轨迹** 上共同分期；
- 亚型 = 标志物异常出现的 **顺序** 不同；
- 整体阶段 = 在该顺序下 **已有多少个事件被触发**（越靠后阶段，触发的事件越多），
  而非每个标志物各算一个阶段再平均。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from staging.biomarker_catalog import BPSD_STAGING_FEATURES, SEQUENTIAL_EVENT_ORDER

DEFAULT_STAGING_JSON = Path("/srv/supercare/task-agent/output/a0_序贯疾病分期结果.json")

# 事件触发阈值：相对队列 z 超过该值视为该序贯事件已发生
EVENT_THRESHOLD_Z = -0.2

SUBTYPE_EVENT_PERMUTATIONS: List[List[str]] = [
    ["cognitive_inverse", "moca_inverse", "npi_total", "adl_dependence"],
    ["npi_total", "cognitive_inverse", "moca_inverse", "adl_dependence"],
    ["adl_dependence", "npi_total", "cognitive_inverse", "moca_inverse"],
]

STAGE_COUNT = 5


def _zscore_matrix(snapshots: List[Dict[str, Any]], features: List[str]) -> Tuple[np.ndarray, List[str]]:
    case_ids: List[str] = []
    rows: List[List[float]] = []
    for snap in snapshots:
        case_ids.append(str(snap.get("case_id", "")))
        row: List[float] = []
        for feature in features:
            value = snap.get(feature)
            row.append(float(value) if value is not None and str(value) != "" else np.nan)
        rows.append(row)
    matrix = np.array(rows, dtype=float)
    for column_index in range(matrix.shape[1]):
        column = matrix[:, column_index]
        median_value = np.nanmedian(column)
        column[np.isnan(column)] = median_value
        std_value = np.nanstd(column)
        if std_value < 1e-6:
            matrix[:, column_index] = 0.0
        else:
            matrix[:, column_index] = (column - np.nanmean(column)) / std_value
    return matrix, case_ids


def _events_reached_from_z(
    z_vector: np.ndarray,
    event_order: List[str],
    feature_index: Dict[str, int],
    threshold: float = EVENT_THRESHOLD_Z,
) -> Tuple[List[str], List[str]]:
    """按序贯顺序判定哪些事件已触发、哪些尚未触发。"""
    reached: List[str] = []
    pending: List[str] = []
    for event in event_order:
        if event not in feature_index:
            pending.append(event)
            continue
        if z_vector[feature_index[event]] > threshold:
            reached.append(event)
        else:
            pending.append(event)
    return reached, pending


def _subtype_fit_score(z_vector: np.ndarray, event_order: List[str], feature_index: Dict[str, int]) -> float:
    """亚型拟合：序贯事件 z 值沿该亚型顺序呈恶化趋势则得分高。"""
    ordered_z = [z_vector[feature_index[event]] for event in event_order if event in feature_index]
    if len(ordered_z) < 2:
        return 0.0
    increasing_pairs = 0
    total_pairs = 0
    for index in range(len(ordered_z) - 1):
        total_pairs += 1
        if ordered_z[index + 1] >= ordered_z[index] - 0.15:
            increasing_pairs += 1
    return increasing_pairs / max(total_pairs, 1)


def _stage_from_sequential_events(events_reached: List[str], event_order: List[str]) -> int:
    """
    整体分期：由序贯事件进展位置决定（全体标志物共用一个阶段）。

    已触发事件数越多，阶段越靠后；映射到 1–5。
    """
    total_events = len([event for event in event_order if event])
    reached_count = len(events_reached)
    if total_events <= 0:
        return 3
    if reached_count <= 0:
        return 1
    # 将 1..total_events 线性映射到 2..5，保证有事件即至少为轻度进展
    stage = int(round((reached_count / total_events) * (STAGE_COUNT - 1))) + 1
    return min(STAGE_COUNT, max(1, stage))


def _stage_label(stage: int) -> str:
    labels = {
        1: "早期（亚临床/轻度）",
        2: "轻度进展期",
        3: "中度进展期",
        4: "中重度期",
        5: "重度/高依赖期",
    }
    return labels.get(stage, f"阶段{stage}")


def infer_staging_from_z_vector(
    z_vector: np.ndarray,
    feature_index: Dict[str, int],
    features: List[str],
) -> Dict[str, Any]:
    """对单时点 z 向量做序贯分期推断（供横截面与纵向共用）。"""
    subtype_scores = [
        (_subtype_fit_score(z_vector, order, feature_index), subtype_index + 1, order)
        for subtype_index, order in enumerate(SUBTYPE_EVENT_PERMUTATIONS)
    ]
    best_score, best_subtype, best_order = max(subtype_scores, key=lambda item: item[0])
    events_reached, events_pending = _events_reached_from_z(z_vector, best_order, feature_index)
    disease_stage = _stage_from_sequential_events(events_reached, best_order)

    event_status = {}
    for event in best_order:
        if event not in feature_index:
            continue
        triggered = event in events_reached
        event_status[event] = {
            "triggered": triggered,
            "zscore": round(float(z_vector[feature_index[event]]), 4),
            "role": "已触发序贯事件" if triggered else "未触发（待进展）",
        }

    return {
        "disease_stage": disease_stage,
        "disease_stage_label": _stage_label(disease_stage),
        "disease_subtype": best_subtype,
        "subtype_confidence": round(float(best_score), 4),
        "event_order": best_order,
        "events_reached": events_reached,
        "events_pending": events_pending,
        "sequential_event_count": len(events_reached),
        "sequential_event_total": len([event for event in best_order if event in feature_index]),
        "event_status": event_status,
        "staging_inference": "全体标志物共享序贯轨迹；阶段=已触发事件在轨迹上的位置，非逐标志物分期平均",
        "biomarker_zscores": {features[i]: round(float(z_vector[i]), 4) for i in range(len(features))},
    }


def run_sequential_staging(cohort_payload: Dict[str, Any], focus_case_id: Optional[str] = None) -> Dict[str, Any]:
    """对队列最新截面运行本地序贯分期。"""
    snapshots = [case.get("latest_snapshot", {}) for case in cohort_payload.get("cases", [])]
    snapshots = [snap for snap in snapshots if snap.get("case_id")]
    candidate_order = [event for event in SEQUENTIAL_EVENT_ORDER if event in BPSD_STAGING_FEATURES]
    features = [event for event in candidate_order if any(snap.get(event) is not None for snap in snapshots)]
    if not features:
        return {"error": "队列中无可用生物标志物，无法分期", "cases": []}

    matrix, case_ids = _zscore_matrix(snapshots, features)
    feature_index = {name: index for index, name in enumerate(features)}

    case_results: List[Dict[str, Any]] = []
    for row_index, case_id in enumerate(case_ids):
        z_vector = matrix[row_index]
        snap = snapshots[row_index]
        inferred = infer_staging_from_z_vector(z_vector, feature_index, features)
        case_results.append(
            {
                "case_id": case_id,
                "folder_name": snap.get("folder_name", ""),
                "is_focus_case": case_id == focus_case_id,
                "latest_biomarkers": {key: snap.get(key) for key in features},
                **inferred,
            }
        )

    focus = next((item for item in case_results if item.get("is_focus_case")), case_results[0] if case_results else None)
    return {
        "model": "本地序贯疾病分期模型（SuperCare）",
        "staging_paradigm": "全体生物标志物在同一序贯轨迹上共同分期；阶段由已触发事件数决定",
        "event_threshold_z": EVENT_THRESHOLD_Z,
        "runtime": "本地流水线 A0，无外部 API/第三方分期服务",
        "event_features": features,
        "stage_count": STAGE_COUNT,
        "subtype_count": len(SUBTYPE_EVENT_PERMUTATIONS),
        "cohort_size": len(case_results),
        "focus_case_id": focus_case_id,
        "focus_case_staging": focus,
        "cases": case_results,
        "gp_care_implications": _gp_implications(focus),
    }


def _gp_implications(focus: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not focus:
        return {}
    stage = int(focus.get("disease_stage", 3))
    subtype = int(focus.get("disease_subtype", 1))
    implications: Dict[str, Any] = {
        "stage": stage,
        "subtype": subtype,
        "sequential_event_count": focus.get("sequential_event_count", 0),
        "monitoring_intensity": "标准",
        "bpsd_prevention_priority": "中",
        "cognitive_intervention": "维持性非药物干预",
        "medication_review_cadence": "每4周",
    }
    if stage >= 4:
        implications.update(
            {
                "monitoring_intensity": "加强（含夜间加密）",
                "bpsd_prevention_priority": "高",
                "medication_review_cadence": "每2周或事件驱动",
            }
        )
    elif stage <= 2:
        implications.update(
            {
                "monitoring_intensity": "常规",
                "bpsd_prevention_priority": "中-低",
                "medication_review_cadence": "每4-8周",
            }
        )
    if subtype == 1:
        implications["dominant_trajectory"] = "认知-行为主导型：优先认知刺激与 BPSD 监测"
    elif subtype == 2:
        implications["dominant_trajectory"] = "行为-认知主导型：优先 BPSD 触发因素管理与环境调整"
    else:
        implications["dominant_trajectory"] = "功能衰退主导型：优先 ADL/跌倒防护与洗澡安全流程"
    return implications


def save_staging_result(payload: Dict[str, Any], output_path: Path = DEFAULT_STAGING_JSON) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
