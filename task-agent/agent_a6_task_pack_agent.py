#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A6 返院任务包智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A6",
    agent_name="Task_Pack_Agent",
    target_user="任务生成",
    duty="输出返院适应期专项任务包。",
    input_desc="ECR对比报告摘要",
    output_desc="《返院适应期专项任务包》PDF",
    tool_names=[
        "tool_风险洞察",
        "tool_照护洞察",
        "tool_个性化健康档案",
        "tool_体征洞察",
        "tool_用药洞察",
        "tool_疾病分期洞察",
        "tool_贝叶斯风险后验",
    ],
    execution_rules=["任务可执行", "优先最新输入", "无依据留空", "任务频次需匹配本地序贯分期阶段与贝叶斯风险等级"],
    output_mode="pdf",
    pdf_title="返院适应期专项任务包",
    output_file_stem="返院适应期专项任务包",
    report_dimensions="服务内容、频次。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a6_input", output_key: str = "a6_output"):
    return build_agent_node(RUNNER, input_key, output_key)
