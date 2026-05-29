#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A11 返院一周综合报告智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A11",
    agent_name="Weekly_Summary_Agent",
    target_user="周报与会诊准备",
    duty="输出返院一周综合报告。",
    input_desc="返院一周事件与干预效果",
    output_desc="《返院一周综合报告》PDF",
    tool_names=["tool_风险洞察", "tool_体征洞察", "tool_用药洞察", "tool_照护服务记录", "tool_健康评估记录", "tool_睡眠记录"],
    execution_rules=["覆盖关键指标", "优先最新输入", "无依据留空"],
    output_mode="pdf",
    pdf_title="返院一周综合报告",
    output_file_stem="返院一周综合报告",
    report_dimensions="时间范围、BPSD事件频次趋势、事件时段分布、干预有效率、药物调整情况、高风险行为摘要、当前关键问题、需决策事项、会诊建议问题清单。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a11_input", output_key: str = "a11_output"):
    return build_agent_node(RUNNER, input_key, output_key)
