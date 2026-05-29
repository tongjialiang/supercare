#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新生成技术报告中的工作流示意图（加大中文字号，提高 DPI）。
输出至 task-agent/output，供技术报告 docx 替换嵌入图。
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path
from typing import List, Tuple

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
COMPETITION_FIGURES = Path("/srv/supercare/比赛文档/交付物/figures")
PROJECT_ROOT = Path(__file__).resolve().parent

# 图5-1
FIG51_NAME = "图5-1_整体技术链路_爱照护序贯贝叶斯超级GP.png"
# 图3
FIG3_NAME = "图3_DataAgent工作流.png"
# 图5 循证
FIG5_EVIDENCE_NAME = "图5_循证知识基座工作流.png"

# 相对上一版再放大（Word 嵌入后仍清晰可读）
FONT_TITLE = 80
FONT_NODE = 44
FONT_SMALL = 36
FONT_FIG51_TITLE = 36
FONT_FIG51_BOX = 22
FONT_FIG51_NOTE = 18
DPI = 250


def _font_candidates() -> List[Path]:
    return [
        PROJECT_ROOT / "fonts" / "SourceHanSansCN-Regular.otf",
        Path("/srv/supercare/assets/fonts_pkg/extracted/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/srv/supercare/assets/fonts/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]


def _load_pil_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _font_candidates():
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _configure_matplotlib_chinese() -> None:
    for path in _font_candidates():
        if path.is_file():
            font_manager.fontManager.addfont(str(path))
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(path)).get_name()
            plt.rcParams["axes.unicode_minus"] = False
            return
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def generate_figure51_narrative() -> Path:
    """图5-1：整体技术链路（爱照护 → 序贯分期 → 贝叶斯 → 超级GP）。"""
    _configure_matplotlib_chinese()
    fig, ax = plt.subplots(figsize=(26, 15))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(
        "整体技术链路：爱照护纵向评估 → 序贯分期 → 贝叶斯风险融合 → 超级GP协同",
        fontsize=FONT_FIG51_TITLE,
        fontweight="bold",
        color="#0f172a",
        pad=24,
    )

    box_font = FONT_FIG51_BOX
    c_data, c_infer, c_tool, c_agent, c_out = "#e0f2fe", "#fef3c7", "#dcfce7", "#ede9fe", "#ffe4e6"

    def draw_box(xy, text, color, width=0.2, height=0.1):
        x, y = xy
        patch = FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.014,rounding_size=0.018",
            linewidth=2.0,
            edgecolor="#1a365d",
            facecolor=color,
        )
        ax.add_patch(patch)
        ax.text(
            x + width / 2,
            y + height / 2,
            text,
            ha="center",
            va="center",
            fontsize=box_font,
            color="#0f172a",
            linespacing=1.25,
        )
        return (x + width / 2, y), (x + width / 2, y + height)

    def draw_arrow(start, end):
        ax.add_patch(
            FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=18, linewidth=2.0, color="#334155")
        )

    # 上行：数据与推断
    draw_box((0.04, 0.78), "爱照护机构\n纵向评估队列\nNPI·认知·ADL", c_data, 0.17, 0.11)
    draw_box((0.26, 0.78), "长者健康\n智能计算图", c_data, 0.17, 0.11)
    draw_box((0.48, 0.78), "生物标志物\n提取", c_infer, 0.15, 0.11)
    draw_box((0.66, 0.78), "序贯分期\nMCMC 1—5级", c_infer, 0.15, 0.11)
    draw_box((0.84, 0.78), "贝叶斯后验\n文献先验+z分数", c_infer, 0.15, 0.11)

    # 中行：工具
    draw_box((0.12, 0.52), "疾病分期\n洞察工具", c_tool, 0.18, 0.1)
    draw_box((0.38, 0.52), "风险后验\n工具", c_tool, 0.18, 0.1)
    draw_box((0.64, 0.52), "图谱洞察\n工具集", c_tool, 0.18, 0.1)

    # 下行：协同
    draw_box((0.06, 0.22), "GP\n协作中枢", c_agent, 0.14, 0.1)
    draw_box((0.24, 0.22), "护士\n协作中枢", c_agent, 0.14, 0.1)
    draw_box((0.42, 0.22), "照护员\n协作中枢", c_agent, 0.14, 0.1)
    draw_box((0.62, 0.22), "返院 D2/D7/D30\n升级与会诊", c_agent, 0.2, 0.1)
    draw_box((0.84, 0.22), "结构化报告\n与语料沉淀", c_out, 0.15, 0.1)

    arrows = [
        (0.125, 0.78, 0.125, 0.62),
        (0.345, 0.78, 0.21, 0.62),
        (0.555, 0.78, 0.47, 0.62),
        (0.735, 0.78, 0.56, 0.62),
        (0.915, 0.78, 0.73, 0.62),
        (0.21, 0.52, 0.13, 0.32),
        (0.47, 0.52, 0.31, 0.32),
        (0.73, 0.52, 0.72, 0.32),
    ]
    for sx, sy, ex, ey in arrows:
        draw_arrow((sx, sy), (ex, ey))

    ax.text(
        0.5,
        0.38,
        "推断层输出可解释分期与升级后验，驱动「证据轮」量化决策",
        ha="center",
        fontsize=FONT_FIG51_NOTE,
        style="italic",
        color="#475569",
    )

    out = OUTPUT_DIR / FIG51_NAME
    fig.tight_layout()
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out


def generate_figure3_dataagent_workflow() -> Path:
    """图3：DataAgent 工作流总览。"""
    image_width, image_height = 5600, 3200
    title_font = _load_pil_font(FONT_TITLE)
    node_font = _load_pil_font(FONT_NODE)
    small_font = _load_pil_font(FONT_SMALL)

    canvas = Image.new("RGB", (image_width, image_height), color=(252, 252, 252))
    draw = ImageDraw.Draw(canvas)

    def draw_node(x: int, y: int, width: int, height: int, text: str, fill_color: Tuple[int, int, int]) -> None:
        draw.rounded_rectangle([x, y, x + width, y + height], radius=24, fill=fill_color, outline=(50, 50, 50), width=4)
        wrapped = textwrap.wrap(text, width=10)
        line_height = 50
        start_y = y + 22
        for line_index, line_text in enumerate(wrapped[:5]):
            draw.text((x + 16, start_y + line_index * line_height), line_text, fill=(20, 20, 20), font=node_font)

    def draw_arrow(start_xy: Tuple[int, int], end_xy: Tuple[int, int], label: str = "") -> None:
        draw.line([start_xy, end_xy], fill=(70, 70, 70), width=6)
        arrow_x, arrow_y = end_xy
        draw.polygon(
            [(arrow_x, arrow_y), (arrow_x - 18, arrow_y - 10), (arrow_x - 18, arrow_y + 10)],
            fill=(70, 70, 70),
        )
        if label:
            mid_x = (start_xy[0] + end_xy[0]) // 2 - 30
            mid_y = (start_xy[1] + end_xy[1]) // 2 - 22
            draw.text((mid_x, mid_y), label, fill=(50, 50, 50), font=small_font)

    draw.text((80, 48), "图3  DataAgent 工作流（长者健康智能计算图）", fill=(0, 0, 0), font=title_font)
    draw.text(
        (80, 140),
        "主流程 + 并行子流程 + 条件分支 + 异常恢复",
        fill=(60, 60, 60),
        font=small_font,
    )

    draw_node(120, 320, 520, 190, "输入接入\nXLSX/多源数据", (255, 245, 210))
    draw_node(720, 320, 560, 190, "文档解析\nMinerU / OpenPyXL", (220, 240, 255))
    draw_node(1380, 320, 560, 190, "数据治理\n清洗/标准化", (220, 255, 230))
    draw_node(2040, 320, 600, 190, "语义增强\n工作表归纳", (243, 226, 255))
    draw_node(2720, 320, 600, 190, "病例总结\n个性化档案", (255, 230, 236))
    draw_node(3400, 320, 640, 190, "健康计算图构建\n洞察+证据", (225, 245, 255))

    draw_node(1140, 680, 560, 180, "并行A\n体征/睡眠", (236, 248, 255))
    draw_node(1760, 680, 560, 180, "并行B\n服药/照护日志", (236, 255, 244))
    draw_node(2380, 680, 560, 180, "并行C\n住院/异常", (255, 240, 236))
    draw_node(3020, 680, 620, 180, "条件分支\n可信度达标入图", (250, 250, 220))

    draw_node(640, 1180, 680, 190, "异常恢复\n解析/模型失败", (255, 230, 230))
    draw_node(1420, 1180, 720, 190, "恢复策略\n重试·降级·记录", (255, 238, 220))
    draw_node(2240, 1180, 640, 190, "输出层\nJSON/PNG/PDF", (230, 245, 230))
    draw_node(2980, 1180, 960, 190, "交付\n计算图+档案+评测", (225, 240, 255))

    draw_arrow((640, 415), (720, 415))
    draw_arrow((1280, 415), (1380, 415))
    draw_arrow((1940, 415), (2040, 415))
    draw_arrow((2620, 415), (2720, 415))
    draw_arrow((3320, 415), (3400, 415))
    draw_arrow((1680, 510), (1420, 680), "并行")
    draw_arrow((2340, 510), (2040, 680), "并行")
    draw_arrow((2880, 510), (2660, 680), "并行")
    draw_arrow((1880, 770), (3020, 730), "汇聚")
    draw_arrow((3720, 770), (3780, 1180), "继续")

    out = OUTPUT_DIR / FIG3_NAME
    canvas.save(out, format="PNG")
    return out


def generate_figure5_evidence_workflow() -> Path:
    """图5：三超循证知识基座（四层语料加工）工作流。"""
    canvas_width, canvas_height = 6400, 3600
    title_font = _load_pil_font(FONT_TITLE)
    node_font = _load_pil_font(FONT_NODE)
    small_font = _load_pil_font(FONT_SMALL)

    image = Image.new("RGB", (canvas_width, canvas_height), color="#f7fbff")
    drawer = ImageDraw.Draw(image)

    def draw_text_block(text: str, box: tuple[int, int, int, int], font: ImageFont.ImageFont, fill: str) -> None:
        x0, y0, x1, y1 = box
        lines = text.split("\n")
        line_height = font.getbbox("中文")[3] - font.getbbox("中文")[1] + 12
        total_height = line_height * len(lines)
        cursor_y = y0 + max(12, (y1 - y0 - total_height) // 2)
        for line_text in lines:
            text_width = font.getbbox(line_text)[2] - font.getbbox(line_text)[0]
            cursor_x = x0 + max(12, (x1 - x0 - text_width) // 2)
            drawer.text((cursor_x, cursor_y), line_text, fill=fill, font=font)
            cursor_y += line_height

    def draw_arrow(start_xy: tuple[int, int], end_xy: tuple[int, int], color: str = "#1f4e79") -> None:
        drawer.line((start_xy, end_xy), fill=color, width=6)
        ax, ay = end_xy
        drawer.polygon([(ax, ay), (ax - 18, ay - 10), (ax - 18, ay + 10)], fill=color)

    drawer.text((80, 40), "图5  三超循证知识基座工作流（四层语料加工）", fill="#0b3d91", font=title_font)
    drawer.text((80, 130), "主链路 + 三角色语料分支 + 异常恢复 + 质量评估", fill="#334e68", font=small_font)

    steps = [
        "载入\n健康计算图",
        "第一层\n行为原始记录",
        "第二层\n照护叙事重建",
        "第三层\n过程成效关联",
        "第四层\n循证规则",
        "语料生成\nSFT",
        "归档\n评估",
    ]
    node_width, node_height = 560, 210
    start_x, start_y = 90, 300
    gap_x = 150
    node_boxes: List[tuple[int, int, int, int]] = []
    for index, step_name in enumerate(steps):
        x0 = start_x + index * (node_width + gap_x)
        y0, y1 = start_y, start_y + node_height
        x1 = x0 + node_width
        node_boxes.append((x0, y0, x1, y1))
        drawer.rounded_rectangle((x0, y0, x1, y1), radius=24, fill="#dceeff", outline="#2c5aa0", width=5)
        draw_text_block(step_name, (x0 + 12, y0 + 12, x1 - 12, y1 - 12), node_font, "#102a43")

    for index in range(len(node_boxes) - 1):
        current_box, next_box = node_boxes[index], node_boxes[index + 1]
        draw_arrow(
            (current_box[2], (current_box[1] + current_box[3]) // 2),
            (next_box[0] - 14, (next_box[1] + next_box[3]) // 2),
        )

    sft_box = node_boxes[-2]
    branch_origin = ((sft_box[0] + sft_box[2]) // 2, sft_box[3])
    role_boxes = [
        (3580, 900, 4320, 1060, "超级医生 Hub\n语料 with/without CoT"),
        (4620, 900, 5360, 1060, "超级护士 Hub\n语料 with/without CoT"),
        (5660, 900, 6300, 1060, "超级照护员 Hub\n语料 with/without CoT"),
    ]
    for x0, y0, x1, y1, role_text in role_boxes:
        drawer.rounded_rectangle((x0, y0, x1, y1), radius=18, fill="#fff5d6", outline="#c58f00", width=4)
        draw_text_block(role_text, (x0 + 10, y0 + 10, x1 - 10, y1 - 10), small_font, "#7a4a00")
        draw_arrow(branch_origin, ((x0 + x1) // 2, y0 - 12), color="#9a6700")

    exception_box = (800, 1420, 1840, 1620)
    fallback_box = (2060, 1420, 3100, 1620)
    drawer.rounded_rectangle(exception_box, radius=20, fill="#ffe7e7", outline="#b42318", width=4)
    drawer.rounded_rectangle(fallback_box, radius=20, fill="#ffe7e7", outline="#b42318", width=4)
    draw_text_block(
        "异常捕获\nJSON失败/超时\n记录堆栈与摘要",
        (exception_box[0] + 12, exception_box[1] + 10, exception_box[2] - 12, exception_box[3] - 10),
        small_font,
        "#7a271a",
    )
    draw_text_block(
        "恢复兜底\n规则模板补齐\n稳定输出",
        (fallback_box[0] + 12, fallback_box[1] + 10, fallback_box[2] - 12, fallback_box[3] - 10),
        small_font,
        "#7a271a",
    )
    draw_arrow(
        ((node_boxes[4][0] + node_boxes[4][2]) // 2, node_boxes[4][3]),
        ((exception_box[0] + exception_box[2]) // 2, exception_box[1] - 12),
        color="#b42318",
    )
    draw_arrow(
        (exception_box[2] + 10, (exception_box[1] + exception_box[3]) // 2),
        (fallback_box[0] - 14, (fallback_box[1] + fallback_box[3]) // 2),
        color="#b42318",
    )
    draw_arrow(
        (fallback_box[2], (fallback_box[1] + fallback_box[3]) // 2),
        (node_boxes[-1][0] - 16, (node_boxes[-1][1] + node_boxes[-1][3]) // 2),
        color="#b42318",
    )

    metrics_box = (800, 1960, 2680, 2240)
    archive_box = (2880, 1960, 5100, 2240)
    drawer.rounded_rectangle(metrics_box, radius=18, fill="#e9fbef", outline="#1d7a46", width=4)
    drawer.rounded_rectangle(archive_box, radius=18, fill="#e9fbef", outline="#1d7a46", width=4)
    draw_text_block(
        "质量评估\n结构化·证据引用·因果表达\n四层 vs 直接生成",
        (metrics_box[0] + 12, metrics_box[1] + 10, metrics_box[2] - 12, metrics_box[3] - 10),
        small_font,
        "#0f5132",
    )
    draw_text_block(
        "归档交付\nJSONL + PDF + 日志 + 测试报告",
        (archive_box[0] + 12, archive_box[1] + 10, archive_box[2] - 12, archive_box[3] - 10),
        small_font,
        "#0f5132",
    )
    draw_arrow(
        ((node_boxes[-1][0] + node_boxes[-1][2]) // 2, node_boxes[-1][3]),
        ((metrics_box[0] + metrics_box[2]) // 2, metrics_box[1] - 12),
        color="#1d7a46",
    )
    draw_arrow(
        (metrics_box[2] + 10, (metrics_box[1] + metrics_box[3]) // 2),
        (archive_box[0] - 14, (archive_box[1] + archive_box[3]) // 2),
        color="#1d7a46",
    )

    out = OUTPUT_DIR / FIG5_EVIDENCE_NAME
    image.save(out, format="PNG")
    return out


def _sync_outputs(paths: List[Path]) -> None:
    COMPETITION_FIGURES.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.is_file():
            shutil.copy2(path, COMPETITION_FIGURES / path.name)
            print(f"已生成: {path}")
            print(f"  同步: {COMPETITION_FIGURES / path.name}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = [
        generate_figure51_narrative(),
        generate_figure3_dataagent_workflow(),
        generate_figure5_evidence_workflow(),
    ]
    # 兼容旧文件名（报告替换脚本用）
    shutil.copy2(paths[0], OUTPUT_DIR / "整体叙事图_本地序贯分期与超级GP协同.png")
    _sync_outputs(paths)


if __name__ == "__main__":
    main()
