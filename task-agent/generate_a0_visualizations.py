#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据 A0 JSON 与 DataSource 纵向数据，生成序贯分期进展图、生物标志物-分期热图、贝叶斯先验后验图。
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import ListedColormap

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
COMPETITION_DELIVERABLE = Path("/srv/supercare/比赛文档/交付物")
STAGING_JSON = OUTPUT_DIR / "a0_序贯疾病分期结果.json"
BAYESIAN_JSON = OUTPUT_DIR / "a0_贝叶斯风险后验.json"

STAGE_COUNT = 5
STAGE_LABELS = ["1\n早期", "2\n轻度", "3\n中度", "4\n中重度", "5\n重度"]
STAGE_COLORS = ["#22c55e", "#84cc16", "#eab308", "#f97316", "#ef4444"]

BIOMARKER_LABELS = {
    "cognitive_inverse": "MMSE认知逆指标",
    "moca_inverse": "MoCA认知逆指标",
    "npi_total": "NPI总分",
    "adl_dependence": "Barthel/ADL依赖度",
}

LOWER_WORSE: set[str] = set()


def _configure_chinese_font() -> None:
    candidates = [
        PROJECT_ROOT / "fonts" / "SourceHanSansCN-Regular.otf",
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ]
    for font_path in candidates:
        if font_path.is_file():
            font_manager.fontManager.addfont(str(font_path))
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
            plt.rcParams["axes.unicode_minus"] = False
            return
    try:
        from generate_practice_knowledge_graph import ensure_chinese_font

        ensure_chinese_font()
        fp = PROJECT_ROOT / "fonts" / "SourceHanSansCN-Regular.otf"
        if fp.is_file():
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(fp)).get_name()
    except Exception:
        pass
    plt.rcParams["axes.unicode_minus"] = False


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _cohort_stats(staging: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
    """各标志物在队列最新截面的均值、标准差。"""
    features = staging.get("event_features", [])
    buckets: Dict[str, List[float]] = {feature: [] for feature in features}
    for case in staging.get("cases", []):
        latest = case.get("latest_biomarkers", {})
        for feature in features:
            value = latest.get(feature)
            if value is not None:
                buckets[feature].append(float(value))
    stats: Dict[str, Tuple[float, float]] = {}
    for feature, values in buckets.items():
        if not values:
            stats[feature] = (0.0, 1.0)
        else:
            arr = np.array(values)
            std = float(np.std(arr))
            stats[feature] = (float(np.mean(arr)), std if std > 1e-6 else 1.0)
    return stats


def _build_longitudinal_progression(
    focus_case_id: str,
    features: List[str],
    event_order: List[str],
    cohort_stats: Dict[str, Tuple[float, float]],
) -> Tuple[List[str], Dict[str, List[Optional[int]]], List[Optional[int]], Dict[str, List[Optional[float]]]]:
    """
    纵向序贯进展：每个时间点用同一套序贯规则推断
    - 各标志物行：该时点该事件是否已触发（1/0），非单独分期
    - 整体序贯分期行：全体标志物共用的阶段 1-5
    """
    sys.path.insert(0, str(PROJECT_ROOT))
    from staging.biomarker_extraction import _discover_case_excels, extract_single_case
    from staging.sequential_staging_model import infer_staging_from_z_vector

    excel_path = None
    folder_name = focus_case_id
    for folder, path in _discover_case_excels():
        if focus_case_id in path.stem.lower():
            excel_path = path
            folder_name = folder
            break
    if excel_path is None:
        return [], {}, [], {}

    payload = extract_single_case(excel_path, folder_name)
    time_map: Dict[str, Dict[str, float]] = defaultdict(dict)
    for row in payload.get("longitudinal", []):
        if row.get("source") != "健康评估记录":
            continue
        time_key = str(row.get("time_key", ""))[:10]
        if not time_key:
            continue
        for feature in features:
            if row.get(feature) is not None:
                time_map[time_key][feature] = float(row[feature])

    times = sorted(time_map.keys())
    feature_index = {name: index for index, name in enumerate(features)}
    triggered_matrix: Dict[str, List[Optional[int]]] = {feature: [] for feature in event_order}
    value_matrix: Dict[str, List[Optional[float]]] = {feature: [] for feature in event_order}
    unified_stages: List[Optional[int]] = []

    for time_key in times:
        z_vector = np.zeros(len(features))
        has_any = False
        for index, feature in enumerate(features):
            value = time_map[time_key].get(feature)
            value_matrix[feature].append(value)
            if value is None:
                continue
            has_any = True
            mean_value, std_value = cohort_stats.get(feature, (value, 1.0))
            z_vector[index] = (value - mean_value) / std_value

        if not has_any:
            unified_stages.append(None)
            for feature in event_order:
                triggered_matrix[feature].append(None)
            continue

        inferred = infer_staging_from_z_vector(z_vector, feature_index, features)
        reached_set = set(inferred.get("events_reached", []))
        unified_stages.append(int(inferred.get("disease_stage", 3)))

        for feature in event_order:
            if time_map[time_key].get(feature) is None:
                triggered_matrix[feature].append(None)
            else:
                triggered_matrix[feature].append(1 if feature in reached_set else 0)

    return times, triggered_matrix, unified_stages, value_matrix


def _progress_index_percent(raw_value: float, baseline: float, abnormal_level: float) -> float:
    """将原始水平映射为 0–100% 进展指数（baseline→abnormal）。"""
    span = abnormal_level - baseline
    if abs(span) < 1e-6:
        return 50.0
    return float(np.clip(100.0 * (raw_value - baseline) / span, -5, 105))


def plot_sustain_disease_progression_curves(staging: Dict[str, Any], output_path: Path) -> None:
    """
    单图展示 n 条疾病进展曲线：横轴=共同分期，纵轴=归一化进展指数（%），
    便于在同一坐标下比较各生物标志物在各分期的相对水平。
    """
    curves_payload = staging.get("progression_curves", {})
    curve_list = curves_payload.get("curves", [])
    focus = staging.get("focus_case_staging", {})
    focus_stage = int(focus.get("disease_stage", 3))
    latest_biomarkers = focus.get("latest_biomarkers", {})
    folder_name = focus.get("folder_name", staging.get("focus_case_id", ""))
    subtype = int(curves_payload.get("subtype", focus.get("disease_subtype", 1)))
    mcmc_diag = staging.get("mcmc_diagnostics", {})

    if not curve_list:
        plt.figure(figsize=(8, 4))
        plt.text(0.5, 0.5, "无 progression_curves 数据，请先运行分期流水线", ha="center")
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        return

    stages = curve_list[0]["stages"]
    palette = ["#2563eb", "#dc2626", "#059669", "#7c3aed", "#ea580c"]
    bar_width = 0.18
    stage_count = len(stages)
    x_positions = np.arange(1, stage_count + 1)

    fig, axes = plt.subplots(2, 1, figsize=(12, 9), height_ratios=[1.35, 1], sharex=True)
    ax_line, ax_bar = axes[0], axes[1]

    for index, curve in enumerate(curve_list):
        feature = curve["feature"]
        fitted_levels = curve["fitted_levels"]
        empirical_means = curve["empirical_means"]
        event_model = curve.get("event_model", {})
        baseline = float(event_model.get("baseline", 0))
        abnormal = float(event_model.get("abnormal_level", baseline + 1))
        color = palette[index % len(palette)]
        label = BIOMARKER_LABELS.get(feature, feature)

        fitted_index = [_progress_index_percent(value, baseline, abnormal) for value in fitted_levels]
        ax_line.plot(
            x_positions,
            fitted_index,
            color=color,
            linewidth=2.5,
            marker="o",
            markersize=7,
            label=label,
            zorder=3,
        )

        empirical_index = [
            _progress_index_percent(mean_value, baseline, abnormal)
            for mean_value in empirical_means
            if mean_value is not None
        ]
        empirical_stages = [
            stage_index + 1
            for stage_index, mean_value in enumerate(empirical_means)
            if mean_value is not None
        ]
        if empirical_stages:
            ax_line.scatter(
                empirical_stages,
                empirical_index,
                s=55,
                c=color,
                alpha=0.35,
                edgecolors="white",
                zorder=2,
            )

        patient_value = latest_biomarkers.get(feature)
        if patient_value is not None:
            patient_index = _progress_index_percent(float(patient_value), baseline, abnormal)
            ax_line.scatter(
                [focus_stage],
                [patient_index],
                s=220,
                c="#f59e0b",
                marker="*",
                edgecolors="#0f172a",
                linewidths=0.8,
                zorder=5,
            )

        bar_offset = (index - (len(curve_list) - 1) / 2) * bar_width
        ax_bar.bar(
            x_positions + bar_offset,
            fitted_index,
            width=bar_width,
            color=color,
            alpha=0.82,
            label=label,
        )

    ax_line.axvline(focus_stage, color="#1d4ed8", linestyle="--", linewidth=1.5, alpha=0.7)
    ax_line.text(
        focus_stage + 0.05,
        102,
        f"焦点病例当前分期 {focus_stage}",
        fontsize=9,
        color="#1d4ed8",
    )
    ax_line.set_ylabel("进展指数 (%)")
    ax_line.set_ylim(-5, 108)
    ax_line.set_xticks(x_positions)
    ax_line.set_xticklabels([f"阶段{s}" for s in stages])
    ax_line.grid(True, alpha=0.25)
    ax_line.legend(loc="upper left", fontsize=9, ncol=2)

    ax_bar.set_ylabel("各分期拟合水平 (%)")
    ax_bar.set_xlabel("疾病分期（全体标志物共用）")
    ax_bar.set_xticks(x_positions)
    ax_bar.set_xticklabels([f"阶段{s}" for s in stages])
    ax_bar.legend(loc="upper left", fontsize=8, ncol=2)
    ax_bar.grid(True, axis="y", alpha=0.2)

    acceptance = mcmc_diag.get("acceptance_rate", "—")
    fig.suptitle(
        f"疾病进展曲线（单图·多标志物）— {folder_name} | 亚型{subtype} | MCMC 接受率 {acceptance}",
        fontsize=13,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.01,
        "上图：各标志物 logistic 拟合曲线（归一化至 baseline→abnormal 为 0–100%）；下图：各分期分桶柱状对比；★=陈女士当前实测",
        ha="center",
        fontsize=9,
        color="#64748b",
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_biomarker_progression_heatmap(
    staging: Dict[str, Any],
    output_path: Path,
) -> None:
    """纵轴=序贯事件（标志物），横轴=时间；格内=事件是否已触发；末行=全体共用的整体序贯分期。"""
    focus_id = staging.get("focus_case_id", "ms_chen")
    focus = staging.get("focus_case_staging", {})
    event_order = focus.get("event_order") or staging.get("event_features", [])
    features = staging.get("event_features", event_order)
    cohort_stats = _cohort_stats(staging)
    times, triggered_matrix, unified_stages, value_matrix = _build_longitudinal_progression(
        focus_id, features, event_order, cohort_stats
    )

    if not times:
        plt.figure(figsize=(8, 4))
        plt.text(0.5, 0.5, "无纵向时间点数据", ha="center")
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close()
        return

    event_rows = []
    y_labels = []
    annotations = []
    for feature in event_order:
        row_vals = triggered_matrix.get(feature, [])
        event_rows.append([np.nan if value is None else value for value in row_vals])
        y_labels.append(BIOMARKER_LABELS.get(feature, feature))
        ann_row = []
        for triggered, raw in zip(row_vals, value_matrix.get(feature, [])):
            if triggered is None:
                ann_row.append("")
            elif triggered == 1:
                ann_row.append(f"已触发\n{raw:.0f}" if raw is not None else "已触发")
            else:
                ann_row.append(f"未触发\n{raw:.0f}" if raw is not None else "未触发")
        annotations.append(ann_row)

    event_rows.append([np.nan if stage is None else stage for stage in unified_stages])
    y_labels.append("整体序贯分期（共用）")
    annotations.append([str(int(stage)) if stage is not None else "" for stage in unified_stages])

    matrix = np.array(event_rows, dtype=float)
    fig = plt.figure(figsize=(max(10, len(times) * 0.9), 1.2 * len(y_labels) + 1))
    gs = fig.add_gridspec(2, 1, height_ratios=[len(event_order), 1.2], hspace=0.35)
    ax_events = fig.add_subplot(gs[0])
    ax_stage = fig.add_subplot(gs[1])

    event_only = matrix[:-1, :]
    cmap_event = ListedColormap(["#e2e8f0", "#16a34a"])
    ax_events.imshow(event_only, aspect="auto", cmap=cmap_event, vmin=0, vmax=1)
    ax_events.set_xticks(range(len(times)))
    ax_events.set_xticklabels(times, rotation=35, ha="right", fontsize=8)
    ax_events.set_yticks(range(len(event_order)))
    ax_events.set_yticklabels([BIOMARKER_LABELS.get(feature, feature) for feature in event_order])
    ax_events.set_ylabel("序贯事件（按亚型顺序）")

    for row_index in range(event_only.shape[0]):
        for col_index in range(event_only.shape[1]):
            if math.isnan(event_only[row_index, col_index]):
                continue
            ax_events.text(
                col_index,
                row_index,
                annotations[row_index][col_index],
                ha="center",
                va="center",
                fontsize=7,
                color="white" if event_only[row_index, col_index] >= 0.5 else "#475569",
            )

    stage_row = matrix[-1:, :]
    ax_stage.imshow(stage_row, aspect="auto", cmap=ListedColormap(STAGE_COLORS), vmin=1, vmax=5)
    ax_stage.set_xticks(range(len(times)))
    ax_stage.set_xticklabels(times, rotation=35, ha="right", fontsize=8)
    ax_stage.set_yticks([0])
    ax_stage.set_yticklabels(["整体序贯分期"])
    ax_stage.set_xlabel("评估时间")
    for col_index, stage in enumerate(unified_stages):
        if stage is None:
            continue
        ax_stage.text(col_index, 0, str(int(stage)), ha="center", va="center", fontsize=10, color="white")

    folder = focus.get("folder_name", focus_id)
    overall = focus.get("disease_stage_label", "")
    fig.suptitle(
        f"序贯进展热图 — {folder}（当前截面：{overall}；阶段由已触发事件数共同决定）",
        fontsize=11,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.01,
        "上行：各时点序贯事件是否触发（非单标志物独立分期）；下行：该时点全体标志物共用的整体阶段 1-5",
        ha="center",
        fontsize=9,
        color="#64748b",
    )
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_sequential_event_trajectory(staging: Dict[str, Any], output_path: Path) -> None:
    """
    序贯事件进展图：横轴=事件在轨迹上的位置（全体标志物共同推进），
    纵轴=各标志物；整体分期由已触发事件数映射到 1-5。
    """
    focus = staging.get("focus_case_staging", {})
    event_order = focus.get("event_order", [])
    zscores = focus.get("biomarker_zscores", {})
    if not zscores and focus.get("latest_biomarkers"):
        cohort_stats = _cohort_stats(staging)
        for feature, value in focus.get("latest_biomarkers", {}).items():
            if value is None:
                continue
            mean_value, std_value = cohort_stats.get(feature, (float(value), 1.0))
            zscores[feature] = (float(value) - mean_value) / std_value
    events_reached = set(focus.get("events_reached", []))
    events_pending = set(focus.get("events_pending", []))
    overall_stage = int(focus.get("disease_stage", 3))
    reached_count = int(focus.get("sequential_event_count", len(events_reached)))
    total_events = int(focus.get("sequential_event_total", len(event_order)))

    fig, ax = plt.subplots(figsize=(11, 6))
    n_events = len(event_order)
    y_positions = list(range(n_events))[::-1]

    # 轨迹底色：已跨越的事件区段
    for slot_index in range(n_events):
        x_center = slot_index + 1
        if slot_index < reached_count:
            ax.axvspan(x_center - 0.45, x_center + 0.45, color="#dcfce7", alpha=0.5, zorder=0)

    for index, feature in enumerate(event_order):
        y_pos = y_positions[index]
        slot_x = index + 1
        z_value = zscores.get(feature, 0.0)
        reached = feature in events_reached

        ax.hlines(y_pos, 0.5, n_events + 0.5, colors="#e2e8f0", linewidth=4, zorder=1)
        color = "#16a34a" if reached else "#cbd5e1"
        ax.scatter(slot_x, y_pos, s=220, c=color, edgecolors="#0f172a", linewidths=1, zorder=3)
        status_text = "已触发" if reached else "未触发"
        ax.annotate(
            f"{status_text}\nz={z_value:.2f}",
            (slot_x, y_pos),
            textcoords="offset points",
            xytext=(14, 0),
            fontsize=9,
            color="#334155",
        )

    # 整体分期映射到顶部 1-5 刻度
    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    stage_ticks = np.linspace(0.5, n_events + 0.5, STAGE_COUNT)
    ax2.set_xticks(stage_ticks)
    ax2.set_xticklabels([f"整体阶段{s}" for s in range(1, STAGE_COUNT + 1)])
    ax2.axvline(stage_ticks[overall_stage - 1], color="#1d4ed8", linestyle="--", linewidth=2)
    ax2.text(
        stage_ticks[overall_stage - 1],
        n_events + 0.3,
        f"当前整体分期 {overall_stage}\n（{reached_count}/{total_events} 个事件已触发）",
        ha="center",
        fontsize=9,
        color="#1d4ed8",
    )

    ax.set_xlim(0.5, n_events + 0.5)
    ax.set_xticks(range(1, n_events + 1))
    ax.set_xticklabels([f"事件{i+1}\n{BIOMARKER_LABELS.get(event_order[i], event_order[i])[:6]}" for i in range(n_events)])
    ax.set_xlabel("序贯事件在轨迹上的位置（全体标志物共同分期，非逐指标平均）")
    ax.set_yticks(y_positions)
    ax.set_yticklabels([BIOMARKER_LABELS.get(feature, feature) for feature in event_order])
    ax.set_ylabel("生物标志物（亚型顺序）")
    ax.set_title(
        f"序贯事件进展图 — {focus.get('folder_name', '')} | 亚型{focus.get('disease_subtype')} "
        f"{focus.get('disease_stage_label', '')}"
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_bayesian_prior_posterior(bayesian: Dict[str, Any], output_path: Path) -> None:
    """贝叶斯先验→似然更新→后验可视化。"""
    prior_prob = float(bayesian.get("priors", {}).get("bpsd_escalation_30d", 0.15))
    posterior_prob = float(bayesian.get("posteriors", {}).get("bpsd_escalation_30d", 0.05))
    updates = bayesian.get("likelihood_updates", [])
    combined_lr = float(bayesian.get("combined_likelihood_ratio", 1.0))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # 左：概率条形
    labels = ["先验\n(仅分期)", "后验\n(分期+标志物)"]
    values = [prior_prob * 100, posterior_prob * 100]
    colors = ["#94a3b8", "#2563eb"]
    bars = axes[0].bar(labels, values, color=colors, width=0.5)
    axes[0].axhline(35, color="#ef4444", linestyle="--", label="GP会诊阈值 35%")
    axes[0].axhline(25, color="#f97316", linestyle=":", label="护士周评阈值 25%")
    axes[0].set_ylabel("BPSD 30天升级概率 (%)")
    axes[0].set_ylim(0, max(40, values[0] * 1.3))
    axes[0].set_title("先验 vs 后验（陈女士）")
    for bar, value in zip(bars, values):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{value:.1f}%", ha="center")
    axes[0].legend(fontsize=8)

    # 右：公式与 LR
    axes[1].axis("off")
    formula_lines = [
        "核心思想：贝叶斯 odds 更新",
        "odds(H) = P(H) / (1-P(H))",
        "odds(H|D) = odds(H) × ∏ LR_i",
        "P(H|D) = odds(H|D) / (1+odds(H|D))",
        "",
        f"先验 P(H) = {prior_prob:.1%}  （阶段{bayesian.get('disease_stage_prior')}）",
        f"合并 LR = {combined_lr:.4f}",
        f"后验 P(H|D) = {posterior_prob:.1%}",
        "",
        "似然更新项：",
    ]
    for item in updates:
        formula_lines.append(
            f"  · {BIOMARKER_LABELS.get(item['feature'], item['feature'])} "
            f"z={item['zscore']:.2f} → LR={item['likelihood_ratio']}"
        )
    axes[1].text(0.05, 0.95, "\n".join(formula_lines), va="top", fontsize=10)
    axes[1].set_title("计算方法")

    fig.suptitle("贝叶斯风险融合：BPSD 30天内升级", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_methodology_markdown(output_path: Path) -> None:
    content = """# A0 计算方法与核心思想

## 一、本地序贯疾病分期模型

### 核心思想（序贯事件模型 + MCMC，本地实现）
- 每个 BPSD 生物标志物对应 **一个序贯事件异常模型**（baseline → abnormal，logistic onset）。
- **亚型**：标志物异常出现的 **顺序** 不同（三种预设轨迹）。
- **整体阶段 1–5**：全体标志物处在 **同一条分期轴** 上，由 Metropolis-Hastings MCMC 推断。
- **疾病进展曲线**：横轴=分期，纵轴=标志物水平；n 个特征 n 条拟合曲线 + 队列经验均值。

### 计算步骤
1. 为当前亚型标定各事件 onset 与 baseline/abnormal；
2. 给定分期 s，用 logistic 计算各标志物期望水平，构造似然；
3. MCMC 交替提议亚型/分期，burn-in 后取后验中位数；
4. `build_progression_curves` 输出各分期拟合值与分桶经验均值。

## 二、贝叶斯风险融合

### 核心思想
- **假设 H**：30 天内 BPSD 升级。
- **先验 P(H)**：由整体疾病阶段查表（阶段2→15%）。
- **证据 D**：各标志物 z-score；优于队列则 LR<1，差于队列则 LR>1。
- **后验**：odds 形式更新，得到会诊/监测阈值判断。

### 公式
`odds(H|D) = odds(H) × LR_1 × LR_2 × …`，`P(H|D) = odds / (1+odds)`

## 三、配图说明
| 文件 | 含义 |
|------|------|
| a0_疾病进展曲线_*.png | **主图**：单图多曲线+分阶段柱状，纵轴为归一化进展指数(%) |
| a0_生物标志物分期进展热图_*.png | 纵向时点：事件触发 + 整体分期 |
| a0_序贯事件进展图_*.png | 序贯事件槽位与 MCMC 分期 |
| a0_贝叶斯先验后验图_*.png | 先验/后验概率与 LR 说明 |
"""
    output_path.write_text(content, encoding="utf-8")


def main() -> None:
    _configure_chinese_font()
    staging = _load_json(STAGING_JSON)
    bayesian = _load_json(BAYESIAN_JSON)
    focus_name = staging.get("focus_case_staging", {}).get("folder_name", "病例")

    paths = {
        "progression_curves": OUTPUT_DIR / f"a0_疾病进展曲线_{focus_name}.png",
        "heatmap": OUTPUT_DIR / f"a0_生物标志物分期进展热图_{focus_name}.png",
        "trajectory": OUTPUT_DIR / f"a0_序贯事件进展图_{focus_name}.png",
        "bayesian": OUTPUT_DIR / f"a0_贝叶斯先验后验图_{focus_name}.png",
        "method": OUTPUT_DIR / "a0_计算方法与核心思想.md",
    }

    plot_sustain_disease_progression_curves(staging, paths["progression_curves"])
    plot_biomarker_progression_heatmap(staging, paths["heatmap"])
    plot_sequential_event_trajectory(staging, paths["trajectory"])
    plot_bayesian_prior_posterior(bayesian, paths["bayesian"])
    write_methodology_markdown(paths["method"])

    COMPETITION_DELIVERABLE.mkdir(parents=True, exist_ok=True)
    import shutil

    for path in paths.values():
        if path.is_file():
            shutil.copy2(path, COMPETITION_DELIVERABLE / path.name)

    print("已生成：")
    for key, path in paths.items():
        print(f"  [{key}] {path}")


if __name__ == "__main__":
    main()
