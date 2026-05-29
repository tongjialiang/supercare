#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A10 三时点趋势对比智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A10",
    agent_name="Trend_Comparison_Agent",
    target_user="图表与趋势",
    duty="输出三时点功能对比图说明。",
    input_desc="三时点数据描述",
    output_desc="《三时点功能对比图》PDF",
    tool_names=["tool_个性化健康档案", "tool_体征洞察", "tool_健康评估记录", "tool_最新时序摘要"],
    execution_rules=["对比清晰", "优先最新输入", "无依据留空"],
    output_mode="pdf",
    pdf_title="三时点功能对比图",
    output_file_stem="三时点功能对比图",
    report_dimensions="住院前、住院时、返院第五天的ADL分值、NPI分值、进食情况、吞咽状况、夜间睡眠、关键变化说明、图表类型、风险等级。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a10_input", output_key: str = "a10_output"):
    return build_agent_node(RUNNER, input_key, output_key)
