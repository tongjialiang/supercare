#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A3 CDA Hub。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A3",
    agent_name="CDA_Hub",
    target_user="GP/精神科团队",
    duty="输出GP确认意见与会诊协同建议。",
    input_desc="会诊问题与目标调整需求",
    output_desc="GP协作专业答复PDF",
    tool_names=[
        "tool_近况摘要",
        "tool_风险洞察",
        "tool_照护洞察",
        "tool_个性化健康档案",
        "tool_体征洞察",
        "tool_用药洞察",
        "tool_健康评估记录",
        "tool_风险照护联动",
        "tool_疾病分期洞察",
        "tool_贝叶斯风险后验",
    ],
    execution_rules=[
        "明确触发条件",
        "优先最新输入",
        "无依据留空",
        "结合本地序贯分期与贝叶斯后验给出针对性 GP 照护方案，注明概率与阶段",
    ],
    output_mode="pdf",
    pdf_title="GP协作专业答复",
    output_file_stem="GP协作专业答复",
    report_dimensions="建议包含：GP确认意见、会诊决策、目标更新、协同分工。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a3_input", output_key: str = "a3_output"):
    return build_agent_node(RUNNER, input_key, output_key)
