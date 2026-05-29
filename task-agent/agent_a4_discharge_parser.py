#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A4 出院摘要解析智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A4",
    agent_name="Discharge_Parser",
    target_user="文档理解",
    duty="将出院摘要结构化为标准字段。",
    input_desc="出院摘要文本",
    output_desc="《出院摘要结构化包》PDF",
    tool_names=["tool_近况摘要", "tool_个性化健康档案", "tool_基础信息", "tool_用药洞察"],
    execution_rules=["字段无依据则留空", "优先最新输入", "正文不限制字数"],
    output_mode="pdf",
    pdf_title="出院摘要结构化包",
    output_file_stem="出院摘要结构化包",
    report_dimensions="住院期间BPSD类型、住院期间BPSD频次、有效干预记录、无效干预记录、药物调整项、出院NPI评分、出院ADL评分、触发因素清单、高风险提示、出院医嘱、返院承接建议、家属配合要求、下次复诊建议时间。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a4_input", output_key: str = "a4_output"):
    return build_agent_node(RUNNER, input_key, output_key)
