#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 CAA Hub。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A1",
    agent_name="CAA_Hub",
    target_user="照护员",
    duty="解答照护执行困惑，给出可执行建议。",
    input_desc="照护员实时问题与现场描述",
    output_desc="照护员协作专业答复PDF",
    tool_names=["tool_老人主体", "tool_近况摘要", "tool_风险洞察", "tool_照护洞察", "tool_体征洞察", "tool_用药洞察", "tool_照护服务记录", "tool_健康评估记录", "tool_睡眠记录"],
    execution_rules=["优先依据最新输入", "输出要可执行", "无依据留空"],
    output_mode="pdf",
    pdf_title="照护员协作专业答复",
    output_file_stem="照护员协作专业答复",
    report_dimensions="建议包含：问题归纳、处理步骤、风险防护、家属沟通、反馈要点。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a1_input", output_key: str = "a1_output"):
    return build_agent_node(RUNNER, input_key, output_key)
