#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A8 升级判断智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A8",
    agent_name="Escalation_Decision_Agent",
    target_user="风险升级",
    duty="评估事件严重程度并给出处置建议。",
    input_desc="BPSD事件报告",
    output_desc="《BPSD 事件处理建议》PDF",
    tool_names=[
        "tool_风险洞察",
        "tool_个性化健康档案",
        "tool_体征洞察",
        "tool_用药洞察",
        "tool_健康评估记录",
        "tool_风险照护联动",
        "tool_疾病分期洞察",
        "tool_贝叶斯风险后验",
    ],
    execution_rules=[
        "先判级后建议",
        "优先最新输入",
        "无依据留空",
        "升级阈值需对照贝叶斯后验与 decision_thresholds，给出概率依据",
    ],
    output_mode="pdf",
    pdf_title="BPSD 事件处理建议",
    output_file_stem="BPSD事件处理建议",
    report_dimensions="处置等级、继续观察条件、护士介入条件、GP介入条件、后续观察重点、升级流程是否触发。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a8_input", output_key: str = "a8_output"):
    return build_agent_node(RUNNER, input_key, output_key)
