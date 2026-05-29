#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A2 CCA Hub。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A2",
    agent_name="CCA_Hub",
    target_user="护士",
    duty="提供评估与周任务指导。",
    input_desc="护士评估问题与数据解读需求",
    output_desc="护士协作专业答复PDF",
    tool_names=["tool_近况摘要", "tool_风险洞察", "tool_照护洞察", "tool_体征洞察", "tool_用药洞察", "tool_健康评估记录", "tool_睡眠记录", "tool_最新时序摘要"],
    execution_rules=["强调D5/D14规范", "优先最新输入", "无依据留空"],
    output_mode="pdf",
    pdf_title="护士协作专业答复",
    output_file_stem="护士协作专业答复",
    report_dimensions="建议包含：评估结论、周重点任务、录入规范、风险观察。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a2_input", output_key: str = "a2_output"):
    return build_agent_node(RUNNER, input_key, output_key)
