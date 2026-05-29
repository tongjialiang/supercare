#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A15 老年健康分期智能体：本地序贯分期 + 贝叶斯，为超级 GP 提供量化分层依据。"""

from pathlib import Path
from typing import Any, Dict

from common_utils import DEFAULT_GRAPH_PATH, AgentSpec, TaskAgentRunner, build_agent_node

SPEC = AgentSpec(
    agent_code="A15",
    agent_name="Health_Staging_Agent",
    target_user="超级全科医师-GP / 护士 / 算法审计",
    duty="解读 DataSource 生物标志物、本地序贯分期与贝叶斯后验，输出可审计的分期报告。",
    input_desc="病例标识或返院照护背景；可选补充最新 NPI/ADL 观测",
    output_desc="《老年健康序贯分期与贝叶斯风险报告》PDF",
    tool_names=["tool_疾病分期洞察", "tool_贝叶斯风险后验", "tool_老人主体", "tool_健康评估记录"],
    execution_rules=[
        "必须先引用 A0 工具中的分期与后验数值，不得编造",
        "说明亚型对应的非药物干预与监测频次差异",
        "给出超级 GP 可执行的分层照护建议",
        "不得引用外部第三方分期产品名称，统一称「本地序贯疾病分期模型」",
    ],
    output_mode="pdf",
    pdf_title="老年健康序贯分期与贝叶斯风险报告",
    output_file_stem="老年健康序贯分期与贝叶斯风险报告",
    report_dimensions=(
        "建议包含：生物标志物摘要、疾病阶段与亚型、序贯事件解释、"
        "贝叶斯后验（BPSD升级/跌倒/照护强度）、GP分层照护方案、与 A3/A8 协同接口。"
    ),
)
RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    return RUNNER.run(user_input=user_input, graph_path=graph_path or DEFAULT_GRAPH_PATH, use_tools=use_tools)


def get_langgraph_node(input_key: str = "a15_input", output_key: str = "a15_output"):
    return build_agent_node(RUNNER, input_key, output_key)
