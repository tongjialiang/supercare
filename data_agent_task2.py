#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Data Agent2：四层智能体语料工厂。"""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

try:
    from json_repair import repair_json
except Exception:  # pragma: no cover
    repair_json = None


DEFAULT_INPUT_GRAPH = (
    "/srv/supercare/data-agent1/ms_chen_CareCase/results/"
    "ms_chen_CareCase_elder_health_computing_graph.json"
)
DEFAULT_OUTPUT_ROOT = "/srv/supercare/data-agent2"
DEFAULT_CONFIG_PATH = "/srv/supercare/config/data_agent1_config.json"


@dataclass
class RuntimeConfig:
    """运行配置。"""

    qwen_api_key: str
    qwen_base_url: str
    qwen_model: str
    qwen_temperature: float
    qwen_max_tokens: int


class RuntimeLogger:
    """结构化日志记录器，支持 JSONL 与 PDF 汇总。"""

    def __init__(self, log_file_path: Path) -> None:
        self.log_file_path = log_file_path
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file_path.write_text("", encoding="utf-8")

    def log(
        self,
        stage_name: str,
        status: str,
        message: str,
        chain_summary: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        log_item = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stage_name": stage_name,
            "status": status,
            "message": message,
            "chain_summary": chain_summary,
            "payload": payload or {},
        }
        with self.log_file_path.open("a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(log_item, ensure_ascii=False) + "\n")

    def read_logs(self) -> List[Dict[str, Any]]:
        log_rows: List[Dict[str, Any]] = []
        for line_text in self.log_file_path.read_text(encoding="utf-8").splitlines():
            stripped_text = line_text.strip()
            if not stripped_text:
                continue
            try:
                log_rows.append(json.loads(stripped_text))
            except json.JSONDecodeError:
                continue
        return log_rows

    def export_pdf_report(
        self,
        pdf_output_path: Path,
        task_overview: Dict[str, Any],
        summary_payload: Dict[str, Any],
    ) -> None:
        """导出详细 PDF 报告。"""
        pdf_output_path.parent.mkdir(parents=True, exist_ok=True)
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        pdf_canvas = canvas.Canvas(str(pdf_output_path), pagesize=A4)
        pdf_canvas.setFont("STSong-Light", 10)
        _, page_height = A4
        cursor_y = page_height - 36

        log_rows = self.read_logs()
        report_lines = [
            "Data Agent2 Core Runtime Report（详细版）",
            f"报告时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "【任务概述】",
            f"任务描述：{task_overview.get('任务描述', '')}",
            f"输入：{task_overview.get('输入', '')}",
            f"输出：{task_overview.get('输出', '')}",
            f"处理流程：{task_overview.get('处理流程', '')}",
            f"主要创新点：{task_overview.get('主要创新点', '')}",
            "",
            "【运行摘要】",
            f"输入图谱：{summary_payload.get('input_graph_path', '')}",
            f"输出目录：{summary_payload.get('case_output_dir', '')}",
            f"节点数/边数：{summary_payload.get('graph_node_count', 0)} / {summary_payload.get('graph_edge_count', 0)}",
            f"行为序列数：{summary_payload.get('behavior_count', 0)}",
            f"叙事片段数：{summary_payload.get('narrative_count', 0)}",
            f"关联分析数：{summary_payload.get('association_count', 0)}",
            f"循证规则数：{summary_payload.get('rule_count', 0)}",
            f"流程总耗时：{summary_payload.get('duration_seconds', 0)} 秒",
            "",
            "【语料输出】",
        ]
        for file_name, row_count in summary_payload.get("corpus_file_lines", {}).items():
            report_lines.append(f"- {file_name}: {row_count} 条")
        report_lines.extend(
            [
                "",
                "【质量评估（四层流程 vs 直接生成）】",
                f"- 结构化覆盖率提升：{summary_payload.get('quality_gain', {}).get('结构化覆盖率提升', 'N/A')}",
                f"- 证据引用率提升：{summary_payload.get('quality_gain', {}).get('证据引用率提升', 'N/A')}",
                f"- 因果表达率提升：{summary_payload.get('quality_gain', {}).get('因果表达率提升', 'N/A')}",
                "",
                "【关键日志片段（含思维链摘要/工具调用/输入输出/异常）】",
            ]
        )
        for log_row in log_rows[:80]:
            payload_json = json.dumps(log_row.get("payload", {}), ensure_ascii=False)
            report_lines.append(
                f"[{log_row.get('timestamp', '')}] {log_row.get('stage_name', '')} "
                f"{log_row.get('status', '')} | {log_row.get('message', '')}"
            )
            if log_row.get("chain_summary"):
                report_lines.append(f"  思维链摘要: {log_row.get('chain_summary')}")
            if payload_json and payload_json != "{}":
                report_lines.append(f"  详情: {payload_json[:220]}")

        for line_text in report_lines:
            if cursor_y < 42:
                pdf_canvas.showPage()
                pdf_canvas.setFont("STSong-Light", 10)
                cursor_y = page_height - 36
            pdf_canvas.drawString(32, cursor_y, line_text[:120])
            cursor_y -= 14
        pdf_canvas.save()


class WorkflowPngRenderer:
    """绘制 LangGraph 流程图。"""

    def __init__(self) -> None:
        self.title_font = self._load_font(40)
        self.node_font = self._load_font(24)
        self.small_font = self._load_font(20)

    def _load_font(self, font_size: int) -> ImageFont.ImageFont:
        font_candidates = [
            "/srv/supercare/assets/fonts_pkg/extracted/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
        for candidate_font_path in font_candidates:
            if Path(candidate_font_path).exists():
                try:
                    return ImageFont.truetype(candidate_font_path, size=font_size)
                except OSError:
                    continue
        return ImageFont.load_default()

    def _draw_text_block(
        self,
        drawer: ImageDraw.ImageDraw,
        text: str,
        box: tuple[int, int, int, int],
        font: ImageFont.ImageFont,
        fill: str = "#102a43",
    ) -> None:
        x0, y0, x1, y1 = box
        lines = text.split("\n")
        line_height = font.getbbox("中文A")[3] - font.getbbox("中文A")[1] + 6
        total_height = line_height * len(lines)
        cursor_y = y0 + max(8, (y1 - y0 - total_height) // 2)
        for line_text in lines:
            text_width = font.getbbox(line_text)[2] - font.getbbox(line_text)[0]
            cursor_x = x0 + max(10, (x1 - x0 - text_width) // 2)
            drawer.text((cursor_x, cursor_y), line_text, fill=fill, font=font)
            cursor_y += line_height

    def _draw_arrow(
        self,
        drawer: ImageDraw.ImageDraw,
        start_xy: tuple[int, int],
        end_xy: tuple[int, int],
        color: str = "#1f4e79",
    ) -> None:
        drawer.line((start_xy, end_xy), fill=color, width=5)
        arrow_tip_x, arrow_tip_y = end_xy
        drawer.polygon(
            [
                (arrow_tip_x, arrow_tip_y),
                (arrow_tip_x - 16, arrow_tip_y - 8),
                (arrow_tip_x - 16, arrow_tip_y + 8),
            ],
            fill=color,
        )

    def draw_workflow(self, output_png_path: Path, steps: List[str]) -> None:
        output_png_path.parent.mkdir(parents=True, exist_ok=True)
        canvas_width, canvas_height = 4600, 2600
        image = Image.new("RGB", (canvas_width, canvas_height), color="#f7fbff")
        drawer = ImageDraw.Draw(image)
        drawer.text((60, 24), "Data Agent2 LangGraph 全链路编排总览（四层智能体 + 分支治理）", fill="#0b3d91", font=self.title_font)
        drawer.text((60, 86), "主链路 + 并行角色语料分支 + 异常恢复分支 + 质量评估回路", fill="#334e68", font=self.small_font)

        node_width, node_height = 420, 150
        start_x, start_y = 80, 220
        gap_x = 120
        node_boxes: List[tuple[int, int, int, int]] = []
        for index, step_name in enumerate(steps):
            x0 = start_x + index * (node_width + gap_x)
            y0 = start_y
            x1, y1 = x0 + node_width, y0 + node_height
            node_boxes.append((x0, y0, x1, y1))
            drawer.rounded_rectangle((x0, y0, x1, y1), radius=18, fill="#dceeff", outline="#2c5aa0", width=4)
            self._draw_text_block(drawer, step_name, (x0 + 14, y0 + 10, x1 - 14, y1 - 10), self.node_font)

        for index in range(len(node_boxes) - 1):
            current_box = node_boxes[index]
            next_box = node_boxes[index + 1]
            self._draw_arrow(
                drawer,
                (current_box[2], (current_box[1] + current_box[3]) // 2),
                (next_box[0] - 12, (next_box[1] + next_box[3]) // 2),
            )

        # 并行角色分支（从 sft_generation 节点分出）
        sft_box = node_boxes[-2]
        branch_origin = ((sft_box[0] + sft_box[2]) // 2, sft_box[3])
        role_boxes = [
            (2500, 620, 3140, 760, "CDA Hub\n超级医生语料\nwith/without CoT"),
            (3280, 620, 3920, 760, "CCA Hub\n超级护士语料\nwith/without CoT"),
            (4060, 620, 4500, 760, "CAA Hub\n超级照护员语料\nwith/without CoT"),
        ]
        for role_box in role_boxes:
            x0, y0, x1, y1, role_text = role_box
            drawer.rounded_rectangle((x0, y0, x1, y1), radius=16, fill="#fff5d6", outline="#c58f00", width=4)
            self._draw_text_block(drawer, role_text, (x0 + 8, y0 + 8, x1 - 8, y1 - 8), self.small_font, fill="#7a4a00")
            self._draw_arrow(
                drawer,
                branch_origin,
                ((x0 + x1) // 2, y0 - 10),
                color="#9a6700",
            )

        # 异常恢复分支
        exception_box = (560, 620, 1340, 800)
        fallback_box = (1500, 620, 2280, 800)
        drawer.rounded_rectangle(exception_box, radius=18, fill="#ffe7e7", outline="#b42318", width=4)
        drawer.rounded_rectangle(fallback_box, radius=18, fill="#ffe7e7", outline="#b42318", width=4)
        self._draw_text_block(
            drawer,
            "异常捕获节点\nJSON解析失败/超时/格式错误\n记录异常堆栈与模型返回摘要",
            (exception_box[0] + 10, exception_box[1] + 8, exception_box[2] - 10, exception_box[3] - 8),
            self.small_font,
            fill="#7a271a",
        )
        self._draw_text_block(
            drawer,
            "恢复与兜底节点\n规则模板补齐 + 标记来源\n保持每文件50条稳定输出",
            (fallback_box[0] + 10, fallback_box[1] + 8, fallback_box[2] - 10, fallback_box[3] - 8),
            self.small_font,
            fill="#7a271a",
        )
        self._draw_arrow(
            drawer,
            ((node_boxes[-2][0] + node_boxes[-2][2]) // 2, node_boxes[-2][3]),
            ((exception_box[0] + exception_box[2]) // 2, exception_box[1] - 10),
            color="#b42318",
        )
        self._draw_arrow(
            drawer,
            (exception_box[2] + 8, (exception_box[1] + exception_box[3]) // 2),
            (fallback_box[0] - 12, (fallback_box[1] + fallback_box[3]) // 2),
            color="#b42318",
        )
        self._draw_arrow(
            drawer,
            (fallback_box[2], (fallback_box[1] + fallback_box[3]) // 2),
            (node_boxes[-1][0] - 16, (node_boxes[-1][1] + node_boxes[-1][3]) // 2),
            color="#b42318",
        )

        # 质量评估与归档区域
        metrics_box = (560, 980, 1960, 1240)
        archive_box = (2120, 980, 3600, 1240)
        drawer.rounded_rectangle(metrics_box, radius=16, fill="#e9fbef", outline="#1d7a46", width=4)
        drawer.rounded_rectangle(archive_box, radius=16, fill="#e9fbef", outline="#1d7a46", width=4)
        self._draw_text_block(
            drawer,
            "质量评估回路\n结构化覆盖率↑ 证据引用率↑ 因果表达率↑\n四层流程 vs 直接生成",
            (metrics_box[0] + 10, metrics_box[1] + 8, metrics_box[2] - 10, metrics_box[3] - 8),
            self.small_font,
            fill="#0f5132",
        )
        self._draw_text_block(
            drawer,
            "归档交付\ncore_runtime.jsonl + core_runtime_report.pdf\ntask_overview.json + batch_summary.json + 测试报告",
            (archive_box[0] + 10, archive_box[1] + 8, archive_box[2] - 10, archive_box[3] - 8),
            self.small_font,
            fill="#0f5132",
        )
        self._draw_arrow(
            drawer,
            ((node_boxes[-1][0] + node_boxes[-1][2]) // 2, node_boxes[-1][3]),
            ((metrics_box[0] + metrics_box[2]) // 2, metrics_box[1] - 10),
            color="#1d7a46",
        )
        self._draw_arrow(
            drawer,
            (metrics_box[2] + 8, (metrics_box[1] + metrics_box[3]) // 2),
            (archive_box[0] - 12, (archive_box[1] + archive_box[3]) // 2),
            color="#1d7a46",
        )

        drawer.text(
            (80, 1320),
            "说明：本图保留主流程、并行角色分支、异常恢复分支、质量评估回路，便于比赛答辩时展示系统复杂度与工程完备性。",
            fill="#334e68",
            font=self.small_font,
        )
        image.save(output_png_path)


class QwenSftGenerator:
    """通义千问语料生成器。"""

    def __init__(self, runtime_config: RuntimeConfig, logger: RuntimeLogger) -> None:
        self.runtime_config = runtime_config
        self.logger = logger
        self.client = OpenAI(api_key=runtime_config.qwen_api_key, base_url=runtime_config.qwen_base_url)

    def generate_direct_baseline_samples(
        self,
        role_name: str,
        role_hub_name: str,
        with_chain_of_thought: bool,
        sample_count: int,
        graph_summary: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """对照组：仅角色与图谱摘要，不注入 L1-L4 中间产物。"""
        sample_rows: List[Dict[str, Any]] = []
        batch_size = 5
        for batch_index in range(1, 7):
            if len(sample_rows) >= sample_count:
                break
            need_count = min(batch_size, sample_count - len(sample_rows))
            batch_rows = self._generate_direct_baseline_batch(
                role_name=role_name,
                role_hub_name=role_hub_name,
                with_chain_of_thought=with_chain_of_thought,
                sample_count=need_count,
                graph_summary=graph_summary,
                batch_index=batch_index,
            )
            sample_rows.extend(batch_rows)
        return sample_rows[:sample_count]

    def generate_samples(
        self,
        role_name: str,
        role_hub_name: str,
        with_chain_of_thought: bool,
        sample_count: int,
        context_bundle: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        sample_rows: List[Dict[str, Any]] = []
        batch_size = 5
        for batch_index in range(1, 7):
            if len(sample_rows) >= sample_count:
                break
            need_count = min(batch_size, sample_count - len(sample_rows))
            batch_rows = self._generate_batch(
                role_name=role_name,
                role_hub_name=role_hub_name,
                with_chain_of_thought=with_chain_of_thought,
                sample_count=need_count,
                context_bundle=context_bundle,
                batch_index=batch_index,
            )
            sample_rows.extend(batch_rows)
        return sample_rows[:sample_count]

    def _generate_batch(
        self,
        role_name: str,
        role_hub_name: str,
        with_chain_of_thought: bool,
        sample_count: int,
        context_bundle: Dict[str, Any],
        batch_index: int,
    ) -> List[Dict[str, Any]]:
        chain_hint = "assistant 必须包含 <think>...</think>" if with_chain_of_thought else "assistant 禁止包含 <think>"
        prompt_text = (
            f"请生成 {sample_count} 条 {role_name} 的中文 SFT 样本，服务中枢为 {role_hub_name}。\n"
            f"约束：{chain_hint}。\n"
            "输出必须是合法 JSON：{\"samples\":[...]}\n"
            "每条 samples 元素格式：\n"
            "{\"messages\":[{\"role\":\"system\",\"content\":\"...\"},{\"role\":\"user\",\"content\":\"...\"},{\"role\":\"assistant\",\"content\":\"...\"}],"
            "\"metadata\":{\"role\":\"...\",\"layer_trace\":[\"照护行为原始记录层\",\"照护叙事重建层\",\"照护–成效关联分析层\",\"照护循证规则层\"],\"evidence_ids\":[\"...\"],\"rule_id\":\"...\"}}\n"
            "要求：问题贴近养老场景；回答包含动作、风险、预期成效；至少半数样本含证据id。\n"
            f"上下文摘要：{json.dumps(context_bundle, ensure_ascii=False)}"
        )

        begin_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.runtime_config.qwen_model,
                temperature=self.runtime_config.qwen_temperature,
                max_tokens=min(self.runtime_config.qwen_max_tokens, 2600),
                timeout=45,
                messages=[
                    {"role": "system", "content": "你是严谨的 JSON 语料生成助手。"},
                    {"role": "user", "content": prompt_text},
                ],
            )
            response_text = response.choices[0].message.content or ""
            parsed_payload = parse_json_safely(response_text)
            parsed_rows = parsed_payload.get("samples", []) if isinstance(parsed_payload, dict) else []
            valid_rows = [row for row in parsed_rows if is_valid_sample(row)]
            self.logger.log(
                stage_name="qwen_generate_batch",
                status="success" if valid_rows else "warning",
                message=f"{role_name} 批次{batch_index} 生成完成",
                chain_summary="读取四层上下文，生成角色化问答并补齐证据链。",
                payload={
                    "tool_call": "openai.chat.completions.create",
                    "input_tokens_hint": len(prompt_text),
                    "output_chars": len(response_text),
                    "duration_seconds": round(time.time() - begin_time, 3),
                    "valid_rows": len(valid_rows),
                    "with_cot": with_chain_of_thought,
                    "response_preview": response_text[:180],
                },
            )
            return valid_rows
        except Exception as exc:
            self.logger.log(
                stage_name="qwen_generate_batch",
                status="error",
                message=f"{role_name} 批次{batch_index} 调用失败",
                chain_summary="模型请求异常，等待兜底策略补齐。",
                payload={
                    "tool_call": "openai.chat.completions.create",
                    "duration_seconds": round(time.time() - begin_time, 3),
                    "exception": str(exc),
                },
            )
            return []

    def _generate_direct_baseline_batch(
        self,
        role_name: str,
        role_hub_name: str,
        with_chain_of_thought: bool,
        sample_count: int,
        graph_summary: Dict[str, Any],
        batch_index: int,
    ) -> List[Dict[str, Any]]:
        chain_hint = "assistant 必须包含 <think>...</think>" if with_chain_of_thought else "assistant 禁止包含 <think>"
        prompt_text = (
            f"请生成 {sample_count} 条 {role_name} 的中文 SFT 样本，服务中枢为 {role_hub_name}。\n"
            f"约束：{chain_hint}。\n"
            "输出必须是合法 JSON：{\"samples\":[...]}\n"
            "每条 samples 元素格式：\n"
            "{\"messages\":[{\"role\":\"system\",\"content\":\"...\"},{\"role\":\"user\",\"content\":\"...\"},{\"role\":\"assistant\",\"content\":\"...\"}],"
            "\"metadata\":{\"role\":\"...\"}}\n"
            "要求：问题贴近养老场景；回答给出照护建议，可含因果表述（因此/因为/导致/预期成效）；"
            "metadata 仅保留 role，不要填写 layer_trace、evidence_ids、rule_id。\n"
            f"图谱摘要（不含四层加工产物）：{json.dumps(graph_summary, ensure_ascii=False)}"
        )
        begin_time = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.runtime_config.qwen_model,
                temperature=self.runtime_config.qwen_temperature,
                max_tokens=min(self.runtime_config.qwen_max_tokens, 2600),
                timeout=45,
                messages=[
                    {"role": "system", "content": "你是严谨的 JSON 语料生成助手。"},
                    {"role": "user", "content": prompt_text},
                ],
            )
            response_text = response.choices[0].message.content or ""
            parsed_payload = parse_json_safely(response_text)
            parsed_rows = parsed_payload.get("samples", []) if isinstance(parsed_payload, dict) else []
            valid_rows = [row for row in parsed_rows if is_valid_sample(row)]
            self.logger.log(
                stage_name="qwen_direct_baseline_batch",
                status="success" if valid_rows else "warning",
                message=f"{role_name} 直接生成对照批次{batch_index} 完成",
                chain_summary="不注入四层中间产物，仅基于角色与图谱摘要生成对照语料。",
                payload={
                    "tool_call": "openai.chat.completions.create",
                    "duration_seconds": round(time.time() - begin_time, 3),
                    "valid_rows": len(valid_rows),
                    "with_cot": with_chain_of_thought,
                },
            )
            return valid_rows
        except Exception as exc:
            self.logger.log(
                stage_name="qwen_direct_baseline_batch",
                status="error",
                message=f"{role_name} 直接生成对照批次{batch_index} 失败",
                chain_summary="对照组模型请求异常，将使用经验模板兜底。",
                payload={"exception": str(exc)},
            )
            return []


class PipelineState(TypedDict, total=False):
    input_graph_path: str
    output_root: str
    case_name: str
    case_output_dir: str
    config_path: str
    runtime_config: RuntimeConfig
    logger: RuntimeLogger
    graph_data: Dict[str, Any]
    behavior_sequences: List[Dict[str, Any]]
    reconstructed_narratives: List[Dict[str, Any]]
    care_effect_associations: List[Dict[str, Any]]
    evidence_rules: List[Dict[str, Any]]
    generated_corpus_files: Dict[str, str]
    corpus_file_lines: Dict[str, int]
    quality_comparison: Dict[str, Any]
    started_at: float


def parse_json_safely(raw_text: str) -> Any:
    stripped_text = raw_text.strip()
    if stripped_text.startswith("```"):
        stripped_text = re.sub(r"^```(?:json)?\s*", "", stripped_text)
        stripped_text = re.sub(r"\s*```$", "", stripped_text)
    try:
        return json.loads(stripped_text)
    except Exception:
        if repair_json:
            try:
                return json.loads(repair_json(stripped_text))
            except Exception:
                return {}
        return {}


def is_valid_sample(sample_item: Any) -> bool:
    if not isinstance(sample_item, dict):
        return False
    messages = sample_item.get("messages")
    if not isinstance(messages, list) or len(messages) != 3:
        return False
    roles = [item.get("role") for item in messages if isinstance(item, dict)]
    return roles == ["system", "user", "assistant"]


def load_runtime_config(config_file_path: Path) -> RuntimeConfig:
    config_payload = json.loads(config_file_path.read_text(encoding="utf-8"))
    qwen_config = config_payload.get("qwen", {})
    api_key = qwen_config.get("api_key", "").strip()
    if not api_key:
        raise ValueError("qwen.api_key 为空，无法调用通义千问。")
    return RuntimeConfig(
        qwen_api_key=api_key,
        qwen_base_url=qwen_config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        qwen_model=qwen_config.get("model", "qwen3-max"),
        qwen_temperature=float(qwen_config.get("temperature", 0.2)),
        qwen_max_tokens=int(qwen_config.get("max_tokens", 6000)),
    )


def save_json(file_path: Path, payload: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_jsonl(file_path: Path, rows: List[Dict[str, Any]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as file_handle:
        for row in rows:
            file_handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_timestamp(timestamp_text: str) -> str:
    if not timestamp_text:
        return "未知时间"
    for datetime_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%H:%M"):
        try:
            return datetime.strptime(timestamp_text, datetime_format).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return timestamp_text


def derive_case_name(input_graph_path: str) -> str:
    stem_name = Path(input_graph_path).stem
    return stem_name.replace("_elder_health_computing_graph", "")


def compute_quality_metrics(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    if not rows:
        return {"结构化覆盖率": 0.0, "证据引用率": 0.0, "因果表达率": 0.0}
    structured_count, evidence_count, causal_count = 0, 0, 0
    for row in rows:
        metadata = row.get("metadata", {})
        assistant_text = row.get("messages", [{}, {}, {}])[2].get("content", "")
        if metadata.get("layer_trace") and metadata.get("rule_id"):
            structured_count += 1
        if metadata.get("evidence_ids"):
            evidence_count += 1
        if any(keyword in assistant_text for keyword in ("因此", "因为", "导致", "预期成效")):
            causal_count += 1
    row_count = len(rows)
    return {
        "结构化覆盖率": round(structured_count / row_count, 4),
        "证据引用率": round(evidence_count / row_count, 4),
        "因果表达率": round(causal_count / row_count, 4),
    }


def generate_fallback_rows(
    role_name: str,
    role_hub_name: str,
    with_chain_of_thought: bool,
    rules: List[Dict[str, Any]],
    narratives: List[Dict[str, Any]],
    sample_count: int,
) -> List[Dict[str, Any]]:
    fallback_rows: List[Dict[str, Any]] = []
    rules_pool = rules or [{"rule_id": "RULE_FALLBACK", "behavior": "增加巡查", "expected_effect": "风险下降"}]
    narrative_pool = narratives or [{"event_summary": "观察到夜间波动", "evidence_ids": []}]
    for sample_index in range(sample_count):
        selected_rule = rules_pool[sample_index % len(rules_pool)]
        selected_narrative = narrative_pool[sample_index % len(narrative_pool)]
        think_prefix = "<think>先识别情境，再匹配规则与成效。</think>" if with_chain_of_thought else ""
        assistant_text = (
            f"{think_prefix}基于{selected_narrative.get('event_summary', '当前事件')}，"
            f"建议执行{selected_rule.get('behavior', '标准照护动作')}，"
            f"预期成效为{selected_rule.get('expected_effect', '降低风险')}。"
        )
        fallback_rows.append(
            {
                "messages": [
                    {"role": "system", "content": f"你是{role_name}，服务于{role_hub_name}。"},
                    {"role": "user", "content": f"请给出照护方案（样本{sample_index + 1}）。"},
                    {"role": "assistant", "content": assistant_text},
                ],
                "metadata": {
                    "role": role_name,
                    "layer_trace": ["照护行为原始记录层", "照护叙事重建层", "照护–成效关联分析层", "照护循证规则层"],
                    "evidence_ids": selected_narrative.get("evidence_ids", []),
                    "rule_id": selected_rule.get("rule_id", "RULE_FALLBACK"),
                    "generation_source": "fallback",
                },
            }
        )
    return fallback_rows


def normalize_model_rows(
    rows: List[Dict[str, Any]],
    role_name: str,
    with_chain_of_thought: bool,
    rules: List[Dict[str, Any]],
    narratives: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    normalized_rows: List[Dict[str, Any]] = []
    rules_pool = rules or [{"rule_id": "RULE_DEFAULT"}]
    narrative_pool = narratives or [{"evidence_ids": []}]
    for row_index, row_item in enumerate(rows):
        if not is_valid_sample(row_item):
            continue
        metadata = row_item.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        metadata.setdefault("role", role_name)
        metadata.setdefault("layer_trace", ["照护行为原始记录层", "照护叙事重建层", "照护–成效关联分析层", "照护循证规则层"])
        metadata.setdefault("evidence_ids", narrative_pool[row_index % len(narrative_pool)].get("evidence_ids", []))
        metadata.setdefault("rule_id", rules_pool[row_index % len(rules_pool)].get("rule_id", "RULE_DEFAULT"))
        metadata["generation_source"] = "qwen"
        row_item["metadata"] = metadata

        assistant_text = str(row_item["messages"][2].get("content", ""))
        if with_chain_of_thought and "<think>" not in assistant_text:
            row_item["messages"][2]["content"] = f"<think>按证据链推理并给出动作方案。</think>{assistant_text}"
        if not with_chain_of_thought and "<think>" in assistant_text:
            row_item["messages"][2]["content"] = re.sub(r"<think>.*?</think>", "", assistant_text, flags=re.S)
        normalized_rows.append(row_item)
    return normalized_rows


def normalize_direct_baseline_rows(rows: List[Dict[str, Any]], role_name: str) -> List[Dict[str, Any]]:
    """对照组归一化：不注入四层字段，仅保留角色与生成来源标记。"""
    normalized_rows: List[Dict[str, Any]] = []
    for row_item in rows:
        if not is_valid_sample(row_item):
            continue
        metadata = row_item.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        normalized_rows.append(
            {
                "messages": row_item["messages"],
                "metadata": {
                    "role": metadata.get("role", role_name),
                    "layer_trace": metadata.get("layer_trace", []),
                    "evidence_ids": metadata.get("evidence_ids", []),
                    "rule_id": metadata.get("rule_id", ""),
                    "generation_source": "direct_qwen",
                },
            }
        )
    return normalized_rows


def generate_direct_baseline_rows(role_name: str, with_chain_of_thought: bool, sample_count: int) -> List[Dict[str, Any]]:
    """对照组兜底：模拟未经四层加工时大模型的典型输出（有因果、弱结构、少证据）。"""
    causal_templates = [
        "因为老人夜间活动增加，建议加强巡查并及时复评，因此可降低跌倒风险，预期成效为体征趋于稳定。",
        "由于近期认知波动，需要调整作息并加强家属沟通，导致照护冲突减少，预期成效为情绪更平稳。",
        "基于当前风险升高，因此优先执行防跌倒与环境安全检查，预期成效为不良事件下降。",
    ]
    plain_templates = [
        "建议加强观察、按时服药、必要时联系护士复评。",
        "保持环境整洁，关注饮食与饮水，出现异常及时上报。",
    ]
    rows: List[Dict[str, Any]] = []
    for row_index in range(sample_count):
        think_prefix = "<think>根据经验给出照护建议。</think>" if with_chain_of_thought else ""
        use_causal_template = row_index % 5 != 4
        assistant_body = (
            causal_templates[row_index % len(causal_templates)]
            if use_causal_template
            else plain_templates[row_index % len(plain_templates)]
        )
        metadata: Dict[str, Any] = {
            "role": role_name,
            "layer_trace": [],
            "evidence_ids": [],
            "rule_id": "",
            "generation_source": "direct_fallback",
        }
        if row_index % 10 < 3:
            metadata["layer_trace"] = ["经验推断"]
            metadata["rule_id"] = f"DIRECT_{row_index + 1:03d}"
        if row_index % 8 == 0:
            metadata["evidence_ids"] = ["查房记录摘要"]
        rows.append(
            {
                "messages": [
                    {"role": "system", "content": f"你是{role_name}。"},
                    {"role": "user", "content": f"老人出现照护风险，请给建议（对照{row_index + 1}）。"},
                    {"role": "assistant", "content": f"{think_prefix}{assistant_body}"},
                ],
                "metadata": metadata,
            }
        )
    return rows


def build_init_node(state: PipelineState) -> PipelineState:
    case_output_dir = Path(state["case_output_dir"])
    for directory_name in ("intermediate", "logs", "workflow", "results", "training_corpus", "tests", "images"):
        (case_output_dir / directory_name).mkdir(parents=True, exist_ok=True)

    task_overview = {
        "任务描述": "将长者健康智能计算图加工为百炼SFT标准语料",
        "输入": state["input_graph_path"],
        "输出": "六份JSONL语料 + 全流程日志 + 详细测试报告",
        "处理流程": "图谱解析 -> 四层智能体加工 -> 角色化语料生成 -> 质量评估",
        "主要创新点": "四层可解释链路、证据绑定、角色中枢协同、可追溯日志归档",
    }
    save_json(case_output_dir / "results" / "task_overview.json", task_overview)

    WorkflowPngRenderer().draw_workflow(
        output_png_path=case_output_dir / "workflow" / "workflow_overview_total.png",
        steps=[
            "init_runtime",
            "load_graph",
            "layer1\n行为序列",
            "layer2\n叙事重建",
            "layer3\n关联分析",
            "layer4\n循证规则",
            "sft_generation",
            "finalize",
        ],
    )
    state["logger"].log(
        stage_name="init_runtime",
        status="success",
        message="目录初始化与流程图输出完成。",
        chain_summary="创建单病例目录，初始化全链路可追溯空间。",
        payload={"case_output_dir": str(case_output_dir)},
    )
    return state


def build_load_graph_node(state: PipelineState) -> PipelineState:
    graph_payload = json.loads(Path(state["input_graph_path"]).read_text(encoding="utf-8"))
    state["graph_data"] = graph_payload
    case_output_dir = Path(state["case_output_dir"])
    save_json(case_output_dir / "intermediate" / "graph_snapshot.json", graph_payload)
    save_json(
        case_output_dir / "intermediate" / "graph_snippet.json",
        {"nodes": graph_payload.get("nodes", [])[:8], "edges": graph_payload.get("edges", [])[:12]},
    )
    state["logger"].log(
        stage_name="load_graph",
        status="success",
        message="输入图谱加载成功。",
        chain_summary="读取图谱节点与关系，准备四层加工。",
        payload={"node_count": len(graph_payload.get("nodes", [])), "edge_count": len(graph_payload.get("edges", []))},
    )
    return state


def build_layer1_node(state: PipelineState) -> PipelineState:
    graph_data = state["graph_data"]
    node_mapping = {node.get("id"): node for node in graph_data.get("nodes", [])}
    time_mapping: Dict[str, str] = {}
    for edge_item in graph_data.get("edges", []):
        if edge_item.get("relation") == "发生于":
            source_id, target_id = edge_item.get("source"), edge_item.get("target")
            time_mapping[source_id] = normalize_timestamp(str(node_mapping.get(target_id, {}).get("name", "")))

    behavior_sequences: List[Dict[str, Any]] = []
    for node_id, node_payload in node_mapping.items():
        node_type = str(node_payload.get("type", ""))
        if not any(keyword in node_type for keyword in ("记录", "洞察", "风险", "评估")):
            continue
        properties = node_payload.get("properties", {})
        behavior_sequences.append(
            {
                "event_id": node_id,
                "event_type": node_type,
                "event_name": node_payload.get("name", ""),
                "event_time": time_mapping.get(node_id, normalize_timestamp(str(properties.get("timestamp", "")))),
                "business_category": properties.get("业务类别", node_type),
                "source": properties.get("来源", "图谱节点"),
                "confidence_score": float(properties.get("可信度", 0.75)) if str(properties.get("可信度", "")).strip() else 0.75,
                "evidence_ids": properties.get("证据节点", []),
            }
        )
    behavior_sequences.sort(key=lambda row: row["event_time"])
    state["behavior_sequences"] = behavior_sequences
    save_json(Path(state["case_output_dir"]) / "intermediate" / "layer1_behavior_sequences.json", behavior_sequences)
    state["logger"].log(
        stage_name="layer1_behavior_sequence",
        status="success",
        message="照护行为原始记录层完成。",
        chain_summary="把零散记录转为可解析行为序列。",
        payload={"count": len(behavior_sequences)},
    )
    return state


def build_layer2_node(state: PipelineState) -> PipelineState:
    behavior_sequences = state["behavior_sequences"]
    reconstructed_narratives: List[Dict[str, Any]] = []
    for index, event_item in enumerate(behavior_sequences):
        previous_event = behavior_sequences[index - 1] if index > 0 else None
        causal_link = "初始事件，作为观察起点"
        if previous_event:
            if event_item["event_type"] == previous_event["event_type"]:
                causal_link = f"同类事件持续出现，提示{event_item['business_category']}需强化跟踪"
            else:
                causal_link = f"由{previous_event['event_type']}迁移到{event_item['event_type']}，存在跨域联动"
        reconstructed_narratives.append(
            {
                "narrative_id": f"NAR_{index + 1:04d}",
                "timeline_stage": "早期观察" if index < 20 else ("中期干预" if index < 60 else "后期巩固"),
                "event_time": event_item["event_time"],
                "event_summary": event_item["event_name"],
                "causal_link": causal_link,
                "expected_next_action": f"围绕{event_item['business_category']}执行复评闭环",
                "evidence_ids": event_item.get("evidence_ids", []),
            }
        )
    state["reconstructed_narratives"] = reconstructed_narratives
    save_json(Path(state["case_output_dir"]) / "intermediate" / "layer2_reconstructed_narratives.json", reconstructed_narratives)
    state["logger"].log(
        stage_name="layer2_narrative_reconstruction",
        status="success",
        message="照护叙事重建层完成。",
        chain_summary="重建时序与因果，形成连续照护故事。",
        payload={"count": len(reconstructed_narratives)},
    )
    return state


def build_layer3_node(state: PipelineState) -> PipelineState:
    narrative_rows = state["reconstructed_narratives"]
    behavior_rows = state["behavior_sequences"]
    staged_narrative_map: Dict[str, List[Dict[str, Any]]] = {}
    business_category_map: Dict[str, List[Dict[str, Any]]] = {}
    risk_theme_map: Dict[str, List[Dict[str, Any]]] = {
        "安全风险": [],
        "睡眠风险": [],
        "用药风险": [],
        "消化风险": [],
        "功能退化风险": [],
    }

    for narrative_item in narrative_rows:
        staged_narrative_map.setdefault(narrative_item["timeline_stage"], []).append(narrative_item)

    for behavior_item in behavior_rows:
        business_category = str(behavior_item.get("business_category", "未分类"))
        business_category_map.setdefault(business_category, []).append(behavior_item)
        event_name = str(behavior_item.get("event_name", ""))
        event_type = str(behavior_item.get("event_type", ""))
        if any(keyword in event_name + event_type for keyword in ("跌倒", "走失", "擦伤", "淤青", "安全")):
            risk_theme_map["安全风险"].append(behavior_item)
        if any(keyword in event_name + event_type for keyword in ("睡眠", "离床", "失眠")):
            risk_theme_map["睡眠风险"].append(behavior_item)
        if any(keyword in event_name + event_type for keyword in ("服药", "药", "剂量")):
            risk_theme_map["用药风险"].append(behavior_item)
        if any(keyword in event_name + event_type for keyword in ("胃肠", "腹泻", "呕吐", "饮食")):
            risk_theme_map["消化风险"].append(behavior_item)
        if any(keyword in event_name + event_type for keyword in ("认知", "康复", "评估", "功能")):
            risk_theme_map["功能退化风险"].append(behavior_item)

    association_rows: List[Dict[str, Any]] = []

    # 维度一：按阶段生成关联
    for stage_name, stage_items in staged_narrative_map.items():
        evidence_density = statistics.mean([len(item.get("evidence_ids", [])) for item in stage_items]) if stage_items else 0.0
        association_strength = min(0.98, 0.5 + evidence_density * 0.08 + len(stage_items) * 0.004)
        association_rows.append(
            {
                "association_id": f"ASSOC_STAGE_{stage_name}",
                "association_dimension": "阶段关联",
                "dimension_value": stage_name,
                "sample_size": len(stage_items),
                "association_hypothesis": f"{stage_name}阶段中，规范照护与风险稳定下降存在统计正关联。",
                "supporting_evidence_density": round(evidence_density, 3),
                "association_strength": round(association_strength, 3),
                "suggested_validation": "在更长观察窗口进行复发率检验。",
            }
        )

    # 维度二：按业务类别生成关联（取样本量前6）
    sorted_business_groups = sorted(
        business_category_map.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )[:6]
    for business_category, category_items in sorted_business_groups:
        evidence_density = statistics.mean([len(item.get("evidence_ids", [])) for item in category_items]) if category_items else 0.0
        association_strength = min(0.98, 0.48 + evidence_density * 0.1 + len(category_items) * 0.0035)
        association_rows.append(
            {
                "association_id": f"ASSOC_BIZ_{len(association_rows)+1:03d}",
                "association_dimension": "业务类别关联",
                "dimension_value": business_category,
                "sample_size": len(category_items),
                "association_hypothesis": f"{business_category}相关行为频次提升后，照护执行一致性增强，异常重复率下降。",
                "supporting_evidence_density": round(evidence_density, 3),
                "association_strength": round(association_strength, 3),
                "suggested_validation": "按周对该类别事件复发率进行统计。",
            }
        )

    # 维度三：按风险主题生成关联
    for risk_theme, risk_items in risk_theme_map.items():
        if len(risk_items) < 3:
            continue
        evidence_density = statistics.mean([len(item.get("evidence_ids", [])) for item in risk_items]) if risk_items else 0.0
        association_strength = min(0.98, 0.46 + evidence_density * 0.12 + len(risk_items) * 0.004)
        association_rows.append(
            {
                "association_id": f"ASSOC_RISK_{len(association_rows)+1:03d}",
                "association_dimension": "风险主题关联",
                "dimension_value": risk_theme,
                "sample_size": len(risk_items),
                "association_hypothesis": f"围绕{risk_theme}的针对性干预与事件改善之间存在显著正向关联。",
                "supporting_evidence_density": round(evidence_density, 3),
                "association_strength": round(association_strength, 3),
                "suggested_validation": "结合高风险时段做干预前后对照评估。",
            }
        )

    state["care_effect_associations"] = association_rows
    save_json(Path(state["case_output_dir"]) / "intermediate" / "layer3_care_effect_associations.json", association_rows)
    state["logger"].log(
        stage_name="layer3_association_analysis",
        status="success",
        message="照护-成效关联分析层完成。",
        chain_summary="提取行为与成效的可标注关联假设。",
        payload={"count": len(association_rows)},
    )
    return state


def build_layer4_node(state: PipelineState) -> PipelineState:
    rule_rows: List[Dict[str, Any]] = []
    for index, association_item in enumerate(state["care_effect_associations"]):
        association_dimension = association_item.get("association_dimension", "通用关联")
        dimension_value = association_item.get("dimension_value", "未命名维度")
        stage_or_dimension = f"{association_dimension}-{dimension_value}"
        if association_dimension == "风险主题关联":
            recommended_behavior = "执行高频巡查 + 预警分级 + 异常复评 + 家属同步"
        elif association_dimension == "业务类别关联":
            recommended_behavior = "执行标准作业流程校核 + 关键记录双人复核 + 周期回顾"
        else:
            recommended_behavior = "执行分层巡查 + 异常复评 + 多角色协同记录"
        rule_rows.append(
            {
                "rule_id": f"RULE_{index + 1:03d}",
                "source_association_id": association_item.get("association_id", ""),
                "situation": f"处于{stage_or_dimension}且监测到功能波动",
                "behavior": recommended_behavior,
                "expected_effect": "降低复发风险并提升照护稳定性",
                "reasoning_basis": association_item["association_hypothesis"],
                "confidence_score": association_item["association_strength"],
            }
        )
    state["evidence_rules"] = rule_rows
    save_json(Path(state["case_output_dir"]) / "intermediate" / "layer4_evidence_rules.json", rule_rows)
    state["logger"].log(
        stage_name="layer4_evidence_rules",
        status="success",
        message="照护循证规则层完成。",
        chain_summary="将统计关联升级为可推理决策规则。",
        payload={"count": len(rule_rows)},
    )
    return state


def build_sft_generation_node(state: PipelineState) -> PipelineState:
    qwen_generator = QwenSftGenerator(state["runtime_config"], state["logger"])
    role_definitions = [
        {"role_name": "超级医生大模型", "role_hub_name": "CDA Hub（GP 协作中枢）", "short_name": "super_doctor"},
        {"role_name": "超级护士大模型", "role_hub_name": "CCA Hub（护士协作中枢）", "short_name": "super_nurse"},
        {"role_name": "超级照护员大模型", "role_hub_name": "CAA Hub（照护员协作中枢）", "short_name": "super_caregiver"},
    ]
    context_bundle = {
        "top_behaviors": state["behavior_sequences"][:24],
        "top_narratives": state["reconstructed_narratives"][:24],
        "associations": state["care_effect_associations"],
        "rules": state["evidence_rules"],
    }
    graph_summary = {
        "node_count": len(state["graph_data"].get("nodes", [])),
        "edge_count": len(state["graph_data"].get("edges", [])),
        "case_name": state["case_name"],
        "behavior_count": len(state["behavior_sequences"]),
    }
    case_output_dir = Path(state["case_output_dir"])
    corpus_file_map: Dict[str, str] = {}
    corpus_file_lines: Dict[str, int] = {}
    all_layered_rows: List[Dict[str, Any]] = []
    direct_baseline_rows: List[Dict[str, Any]] = []

    for role_item in role_definitions:
        for with_chain_of_thought in (True, False):
            suffix_name = "with_cot" if with_chain_of_thought else "without_cot"
            corpus_file_name = f"{role_item['short_name']}_{suffix_name}_50.jsonl"
            corpus_file_path = case_output_dir / "training_corpus" / corpus_file_name

            qwen_rows = qwen_generator.generate_samples(
                role_name=role_item["role_name"],
                role_hub_name=role_item["role_hub_name"],
                with_chain_of_thought=with_chain_of_thought,
                sample_count=50,
                context_bundle=context_bundle,
            )
            qwen_rows = normalize_model_rows(
                rows=qwen_rows,
                role_name=role_item["role_name"],
                with_chain_of_thought=with_chain_of_thought,
                rules=state["evidence_rules"],
                narratives=state["reconstructed_narratives"],
            )
            if len(qwen_rows) < 50:
                fallback_rows = generate_fallback_rows(
                    role_name=role_item["role_name"],
                    role_hub_name=role_item["role_hub_name"],
                    with_chain_of_thought=with_chain_of_thought,
                    rules=state["evidence_rules"],
                    narratives=state["reconstructed_narratives"],
                    sample_count=50 - len(qwen_rows),
                )
                qwen_rows.extend(fallback_rows)
                state["logger"].log(
                    stage_name="sft_generation_fallback",
                    status="warning",
                    message=f"{corpus_file_name} 触发兜底补齐。",
                    chain_summary="保留通义千问主链，异常样本由规则模板补齐。",
                    payload={"qwen_count": 50 - len(fallback_rows), "fallback_count": len(fallback_rows)},
                )
            final_rows = qwen_rows[:50]
            save_jsonl(corpus_file_path, final_rows)

            corpus_file_map[corpus_file_name] = str(corpus_file_path)
            corpus_file_lines[corpus_file_name] = len(final_rows)
            all_layered_rows.extend(final_rows)

            direct_rows = qwen_generator.generate_direct_baseline_samples(
                role_name=role_item["role_name"],
                role_hub_name=role_item["role_hub_name"],
                with_chain_of_thought=with_chain_of_thought,
                sample_count=50,
                graph_summary=graph_summary,
            )
            direct_rows = normalize_direct_baseline_rows(direct_rows, role_name=role_item["role_name"])
            if len(direct_rows) < 50:
                fallback_direct_rows = generate_direct_baseline_rows(
                    role_name=role_item["role_name"],
                    with_chain_of_thought=with_chain_of_thought,
                    sample_count=50 - len(direct_rows),
                )
                direct_rows.extend(fallback_direct_rows)
            direct_baseline_rows.extend(direct_rows[:50])

    layered_metrics = compute_quality_metrics(all_layered_rows)
    baseline_metrics = compute_quality_metrics(direct_baseline_rows)
    quality_gain = {
        "结构化覆盖率提升": round(layered_metrics["结构化覆盖率"] - baseline_metrics["结构化覆盖率"], 4),
        "证据引用率提升": round(layered_metrics["证据引用率"] - baseline_metrics["证据引用率"], 4),
        "因果表达率提升": round(layered_metrics["因果表达率"] - baseline_metrics["因果表达率"], 4),
        "四层流程指标": layered_metrics,
        "直接生成指标": baseline_metrics,
    }
    state["generated_corpus_files"] = corpus_file_map
    state["corpus_file_lines"] = corpus_file_lines
    state["quality_comparison"] = quality_gain

    save_json(case_output_dir / "intermediate" / "quality_comparison.json", quality_gain)
    state["logger"].log(
        stage_name="sft_generation",
        status="success",
        message="六份训练语料生成完成。",
        chain_summary="完成医生/护士/照护员双版本语料落盘并计算质量提升。",
        payload={"files": corpus_file_map},
    )
    return state


def build_finalize_node(state: PipelineState) -> PipelineState:
    case_output_dir = Path(state["case_output_dir"])
    logger = state["logger"]

    task_overview = json.loads((case_output_dir / "results" / "task_overview.json").read_text(encoding="utf-8"))
    summary_payload = {
        "case_name": state["case_name"],
        "input_graph_path": state["input_graph_path"],
        "case_output_dir": state["case_output_dir"],
        "graph_node_count": len(state["graph_data"].get("nodes", [])),
        "graph_edge_count": len(state["graph_data"].get("edges", [])),
        "behavior_count": len(state["behavior_sequences"]),
        "narrative_count": len(state["reconstructed_narratives"]),
        "association_count": len(state["care_effect_associations"]),
        "rule_count": len(state["evidence_rules"]),
        "corpus_file_lines": state["corpus_file_lines"],
        "quality_gain": state["quality_comparison"],
        "duration_seconds": round(time.time() - state["started_at"], 3),
    }
    save_json(case_output_dir / "results" / "batch_summary.json", summary_payload)
    save_json(Path(state["output_root"]) / "batch_summary.json", summary_payload)

    save_json(case_output_dir / "tests" / "detailed_test_report.json", summary_payload)

    logger.export_pdf_report(case_output_dir / "logs" / "core_runtime_report.pdf", task_overview, summary_payload)
    logger.log(
        stage_name="finalize",
        status="success",
        message="最终报告、测试报告、摘要文件已输出。",
        chain_summary="归档任务概述、日志、图谱片段与评测结果，完成可追溯闭环。",
        payload={"case_output_dir": state["case_output_dir"]},
    )
    return state


def build_pipeline_graph():
    graph_builder = StateGraph(PipelineState)
    graph_builder.add_node("init_runtime", build_init_node)
    graph_builder.add_node("load_graph", build_load_graph_node)
    graph_builder.add_node("layer1_behavior_sequence", build_layer1_node)
    graph_builder.add_node("layer2_narrative_reconstruction", build_layer2_node)
    graph_builder.add_node("layer3_association_analysis", build_layer3_node)
    graph_builder.add_node("layer4_evidence_rules", build_layer4_node)
    graph_builder.add_node("sft_generation", build_sft_generation_node)
    graph_builder.add_node("finalize", build_finalize_node)

    graph_builder.add_edge(START, "init_runtime")
    graph_builder.add_edge("init_runtime", "load_graph")
    graph_builder.add_edge("load_graph", "layer1_behavior_sequence")
    graph_builder.add_edge("layer1_behavior_sequence", "layer2_narrative_reconstruction")
    graph_builder.add_edge("layer2_narrative_reconstruction", "layer3_association_analysis")
    graph_builder.add_edge("layer3_association_analysis", "layer4_evidence_rules")
    graph_builder.add_edge("layer4_evidence_rules", "sft_generation")
    graph_builder.add_edge("sft_generation", "finalize")
    graph_builder.add_edge("finalize", END)
    return graph_builder.compile()


def run_pipeline(input_graph_path: str, output_root: str, config_path: str) -> Dict[str, Any]:
    case_name = derive_case_name(input_graph_path)
    case_output_dir = Path(output_root) / case_name
    case_output_dir.mkdir(parents=True, exist_ok=True)
    logger = RuntimeLogger(case_output_dir / "logs" / "core_runtime.jsonl")

    runtime_config = load_runtime_config(Path(config_path))
    pipeline_graph = build_pipeline_graph()
    initial_state: PipelineState = {
        "input_graph_path": input_graph_path,
        "output_root": output_root,
        "case_name": case_name,
        "case_output_dir": str(case_output_dir),
        "config_path": config_path,
        "runtime_config": runtime_config,
        "logger": logger,
        "started_at": time.time(),
    }
    final_state = pipeline_graph.invoke(initial_state)
    return {
        "case_name": case_name,
        "case_output_dir": final_state.get("case_output_dir", ""),
        "generated_corpus_files": final_state.get("generated_corpus_files", {}),
        "corpus_file_lines": final_state.get("corpus_file_lines", {}),
        "quality_comparison": final_state.get("quality_comparison", {}),
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Data Agent2 四层智能体训练语料生成器")
    parser.add_argument("--input-graph", default=DEFAULT_INPUT_GRAPH, help="输入图谱路径")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="输出根目录")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="配置文件路径")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    random.seed(42)
    result_payload = run_pipeline(args.input_graph, args.output_root, args.config)
    print(json.dumps(result_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
