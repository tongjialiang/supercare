#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A14 审计评估智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A14",
    agent_name="Audit_Eval_Agent",
    target_user="审计评估",
    duty="评估任务链路质量与可追溯性。",
    input_desc="任务摘要与输出清单",
    output_desc="《TaskAgent审计评估报告》PDF",
    tool_names=["tool_任务决策摘要", "tool_风险照护联动", "tool_最新时序摘要", "tool_老人主体"],
    execution_rules=["审计可复核", "优先最新输入", "无依据留空"],
    output_mode="pdf",
    pdf_title="TaskAgent审计评估报告",
    output_file_stem="TaskAgent审计评估报告",
    report_dimensions="测试目的、测试内容、测试方法、测试过程、测试结果；并说明使用工具与不使用工具的差异结论。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a14_input", output_key: str = "a14_output"):
    return build_agent_node(RUNNER, input_key, output_key)
