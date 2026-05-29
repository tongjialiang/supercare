#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A7 事件结构化智能体。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A7",
    agent_name="Event_Structuring_Agent",
    target_user="事件解析",
    duty="将事件记录结构化为BPSD事件报告。",
    input_desc="照护员文字/语音转文字",
    output_desc="《BPSD 事件报告》PDF",
    tool_names=["tool_老人主体", "tool_近况摘要", "tool_风险洞察", "tool_照护服务记录", "tool_健康评估记录"],
    execution_rules=["字段齐全", "优先最新输入", "无依据留空"],
    output_mode="pdf",
    pdf_title="BPSD 事件报告",
    output_file_stem="BPSD事件报告",
    report_dimensions="事件日期、事件时间、事件发生场景、事件行为类型、是否复合事件、初始风险等级、照护员应对方式、稳定时长、是否已通知护士、是否触发升级、事件前30分钟描述、护理员判断原因、患者即时反应、现场图片/音频索引。",
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a7_input", output_key: str = "a7_output"):
    return build_agent_node(RUNNER, input_key, output_key)
