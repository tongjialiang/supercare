#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A5 状态对比智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A5",
    agent_name="Baseline_Compare",
    target_user="数据对比",
    duty="输出ECR状态对比报告。",
    input_desc="住院前与出院时摘要",
    output_desc="《ECR 状态对比报告》PDF",
    tool_names=["tool_近况摘要", "tool_个性化健康档案", "tool_基础信息", "tool_体征洞察", "tool_健康评估记录"],
    execution_rules=["变化方向清晰", "优先最新输入", "无依据留空"],
    output_mode="pdf",
    pdf_title="ECR 状态对比报告",
    output_file_stem="ECR状态对比报告",
    report_dimensions="住院前状态摘要、出院时状态摘要、ADL变化、NPI变化、进食状态变化、睡眠状态变化、吞咽风险变化、关键退化项、新增风险点、重点观察项、承接建议级别、既往行为模式对比、约束措施、环境适应性变化。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a5_input", output_key: str = "a5_output"):
    return build_agent_node(RUNNER, input_key, output_key)
