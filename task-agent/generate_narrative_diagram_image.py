#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将整体叙事图导出为 PNG/JPG（含文献先验节点，中文自动换行）。"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path("/srv/supercare/task-agent/output")
COMPETITION_DIR = Path("/srv/supercare/比赛文档")
DELIVERABLE_DIR = COMPETITION_DIR / "交付物"
PROJECT_ROOT = Path("/srv/supercare/task-agent")
BASE_NAME = "整体叙事图_本地序贯分期与超级GP协同"

# 画布与字号（Word 嵌入后仍清晰）
CANVAS_WIDTH = 5200
CANVAS_HEIGHT = 3400
FONT_TITLE = 52
FONT_NODE = 30
FONT_SMALL = 24
FONT_NOTE = 22

# 文献校准先验阶段值（与 staging/prior_literature.py 一致，PNG 内用分行短句展示）

def _font_candidates() -> List[Path]:
    return [
        PROJECT_ROOT / "fonts" / "SourceHanSansCN-Regular.otf",
        Path("/srv/supercare/assets/fonts_pkg/extracted/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/srv/supercare/assets/fonts/NotoSansCJKsc-Regular.otf"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    ]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for font_path in _font_candidates():
        if font_path.is_file():
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_paragraph(paragraph: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    if not paragraph.strip():
        return [""]
    wrapped_lines: List[str] = []
    current_line = ""
    for char in paragraph:
        candidate = current_line + char
        if draw.textlength(candidate, font=font) <= max_width:
            current_line = candidate
        else:
            if current_line:
                wrapped_lines.append(current_line)
            current_line = char
    if current_line:
        wrapped_lines.append(current_line)
    return wrapped_lines or [paragraph]


def _layout_text_lines(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    lines: List[str] = []
    for paragraph in text.split("\n"):
        lines.extend(_wrap_paragraph(paragraph, font, max_width, draw))
    return lines


def _line_block_height(line_count: int, font: ImageFont.FreeTypeFont, line_gap: int = 8) -> int:
    return line_count * (font.size + line_gap)


def draw_text_box(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    height: int,
    text: str,
    fill_color: Tuple[int, int, int],
    font: ImageFont.FreeTypeFont,
    padding: int = 18,
) -> Tuple[int, int, int, int]:
    """绘制圆角文本框，文本自动换行并垂直居中。"""
    draw.rounded_rectangle(
        [x, y, x + width, y + height],
        radius=20,
        fill=fill_color,
        outline=(26, 54, 93),
        width=3,
    )
    max_text_width = width - padding * 2
    lines = _layout_text_lines(text, font, max_text_width, draw)
    block_height = _line_block_height(len(lines), font)
    cursor_y = y + max(padding, (height - block_height) // 2)
    for line in lines:
        line_width = draw.textlength(line, font=font)
        cursor_x = x + (width - line_width) // 2
        draw.text((cursor_x, cursor_y), line, fill=(15, 23, 42), font=font)
        cursor_y += font.size + 8
    return x, y, x + width, y + height


def draw_arrow(
    draw: ImageDraw.ImageDraw,
    start: Tuple[int, int],
    end: Tuple[int, int],
    color: Tuple[int, int, int] = (51, 65, 85),
) -> None:
    draw.line([start, end], fill=color, width=5)
    end_x, end_y = end
    if abs(end_x - start[0]) >= abs(end_y - start[1]):
        direction = 1 if end_x > start[0] else -1
        draw.polygon(
            [(end_x, end_y), (end_x - 18 * direction, end_y - 10), (end_x - 18 * direction, end_y + 10)],
            fill=color,
        )
    else:
        direction = 1 if end_y > start[1] else -1
        draw.polygon(
            [(end_x, end_y), (end_x - 10, end_y - 18 * direction), (end_x + 10, end_y - 18 * direction)],
            fill=color,
        )


def _box_center_bottom(box: Tuple[int, int, int, int]) -> Tuple[int, int]:
    return (box[0] + (box[2] - box[0]) // 2, box[3])


def _box_center_top(box: Tuple[int, int, int, int]) -> Tuple[int, int]:
    return (box[0] + (box[2] - box[0]) // 2, box[1])


def main() -> None:
    title_font = _load_font(FONT_TITLE)
    node_font = _load_font(FONT_NODE)
    note_font = _load_font(FONT_NOTE)

    canvas = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), color=(252, 252, 252))
    draw = ImageDraw.Draw(canvas)

    draw.text(
        (80, 40),
        "SuperCare：DataSource → 本地序贯分期 → 文献先验 → 贝叶斯后验 → 超级GP",
        fill=(15, 23, 42),
        font=title_font,
    )
    draw.text(
        (80, 120),
        "全部本地运行 · 文献校准先验 P(H|stage) 驱动 BPSD 30 天升级后验 · 2026-05-25",
        fill=(71, 85, 105),
        font=note_font,
    )

    c_data = (224, 242, 254)
    c_a0 = (254, 243, 199)
    c_prior = (255, 237, 213)
    c_tool = (220, 252, 231)
    c_agent = (237, 233, 254)
    c_out = (255, 228, 230)

    # 第一行：数据源
    box_ds = draw_text_box(
        draw, 120, 220, 520, 170, "DataSource\n10 例机构病例 Excel", c_data, node_font
    )
    box_graph = draw_text_box(
        draw, 720, 220, 520, 170, "长者健康智能计算图\ndata-agent1 输出", c_data, node_font
    )

    # 第二行：A0 流水线（含文献先验）
    box_excel = draw_text_box(
        draw,
        120,
        480,
        460,
        200,
        "生物标志物矩阵\na0_老年健康生物标志物矩阵.xlsx",
        c_a0,
        node_font,
    )
    box_stage = draw_text_box(
        draw,
        660,
        480,
        460,
        210,
        "本地序贯疾病分期\nMCMC 阶段 1-5\n亚型 1-3",
        c_a0,
        node_font,
    )
    box_prior = draw_text_box(
        draw,
        1160,
        450,
        720,
        270,
        "文献校准先验\nP(H|stage)\n1期早期 6%\n2期轻度 14%\n3期中度 26%\n4期中重度 36%\n5期重度 50%",
        c_prior,
        _load_font(FONT_SMALL),
        padding=20,
    )
    box_bayes = draw_text_box(
        draw,
        1980,
        480,
        540,
        210,
        "贝叶斯后验更新\nz 分数似然比\n阈值 35% / 25% / 20%",
        c_a0,
        node_font,
    )

    # 第三行：工具层
    box_t1 = draw_text_box(draw, 280, 820, 560, 160, "tool_疾病分期洞察", c_tool, node_font)
    box_t2 = draw_text_box(draw, 1020, 820, 620, 160, "tool_贝叶斯风险后验", c_tool, node_font)
    box_t3 = draw_text_box(draw, 2060, 820, 560, 160, "图谱洞察工具集\n风险 / 体征 / 用药", c_tool, node_font)

    # 第四行：协同智能体
    box_a3 = draw_text_box(draw, 180, 1120, 380, 170, "A3\n超级 GP", c_agent, node_font)
    box_a6 = draw_text_box(draw, 640, 1120, 380, 170, "A6\n返院任务包", c_agent, node_font)
    box_a8 = draw_text_box(draw, 1100, 1120, 380, 170, "A8\nBPSD 升级", c_agent, node_font)
    box_a15 = draw_text_box(draw, 1560, 1120, 420, 170, "A15\n分期与风险报告", c_agent, node_font)

    # 第五行：产出
    box_pdf3 = draw_text_box(draw, 520, 1420, 680, 150, "a3_GP协作专业答复.pdf", c_out, node_font)
    box_pdf15 = draw_text_box(
        draw, 1280, 1420, 980, 160, "a15_序贯分期与\n贝叶斯风险报告.pdf", c_out, node_font
    )

    # 纵向/横向箭头
    draw_arrow(draw, _box_center_bottom(box_ds), _box_center_top(box_excel))
    draw_arrow(draw, _box_center_bottom(box_excel), _box_center_top(box_stage))
    draw_arrow(draw, _box_center_bottom(box_stage), _box_center_top(box_prior))
    draw_arrow(draw, _box_center_bottom(box_prior), _box_center_top(box_bayes))

    draw_arrow(draw, _box_center_bottom(box_stage), (box_t1[0] + (box_t1[2] - box_t1[0]) // 2, box_t1[1]))
    draw_arrow(draw, _box_center_bottom(box_bayes), (box_t2[0] + (box_t2[2] - box_t2[0]) // 2, box_t2[1]))
    draw_arrow(draw, _box_center_bottom(box_graph), (box_t3[0] + (box_t3[2] - box_t3[0]) // 2, box_t3[1]))

    draw_arrow(draw, _box_center_bottom(box_t1), (box_a3[0] + (box_a3[2] - box_a3[0]) // 2, box_a3[1]))
    draw_arrow(draw, _box_center_bottom(box_t2), (box_a8[0] + (box_a8[2] - box_a8[0]) // 2, box_a8[1]))
    draw_arrow(draw, _box_center_bottom(box_t1), (box_a15[0] + (box_a15[2] - box_a15[0]) // 2, box_a15[1]))

    draw_arrow(draw, _box_center_bottom(box_a3), (box_pdf3[0] + (box_pdf3[2] - box_pdf3[0]) // 2, box_pdf3[1]))
    draw_arrow(draw, _box_center_bottom(box_a15), (box_pdf15[0] + (box_pdf15[2] - box_pdf15[0]) // 2, box_pdf15[1]))

    draw.text(
        (120, 1680),
        "创新点：MCMC 分期 → 文献校准先验 → 标志物似然更新 → 可审计概率决策 → 超级 GP 协同",
        fill=(71, 85, 105),
        font=note_font,
    )

    png_path = OUTPUT_DIR / f"{BASE_NAME}.png"
    jpg_path = OUTPUT_DIR / f"{BASE_NAME}.jpg"
    canvas.save(png_path, format="PNG", optimize=True)
    canvas.convert("RGB").save(jpg_path, format="JPEG", quality=92)

    DELIVERABLE_DIR.mkdir(parents=True, exist_ok=True)
    COMPETITION_DIR.mkdir(parents=True, exist_ok=True)
    for path in (png_path, jpg_path):
        shutil.copy2(path, DELIVERABLE_DIR / path.name)

    competition_md = COMPETITION_DIR / "7_整体叙事图_本地序贯分期与超级GP协同.md"
    if competition_md.is_file():
        shutil.copy2(competition_md, DELIVERABLE_DIR / competition_md.name)

    print(f"PNG: {png_path}")
    print(f"已同步至: {DELIVERABLE_DIR}")


if __name__ == "__main__":
    main()
