#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A12 会诊记录智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A12",
    agent_name="Consult_Agent",
    target_user="D7会诊",
    duty="输出精神科远程会诊记录。",
    input_desc="周报与新发生状况",
    output_desc="《精神科远程会诊记录》PDF",
    tool_names=["tool_风险洞察", "tool_个性化健康档案", "tool_体征洞察", "tool_用药洞察", "tool_健康评估记录"],
    execution_rules=["会诊字段完整", "优先最新输入", "无依据留空"],
    output_mode="pdf",
    pdf_title="精神科远程会诊记录",
    output_file_stem="精神科远程会诊记录",
    report_dimensions="会诊日期、参会人员、问题摘要、会诊结论、药物调整建议、非药物干预建议、后续观察重点、下次复诊时间、待执行事项、备注。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a12_input", output_key: str = "a12_output"):
    return build_agent_node(RUNNER, input_key, output_key)
