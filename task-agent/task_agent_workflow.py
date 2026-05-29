#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TaskAgent 总工作流。"""

from __future__ import annotations

from typing import Any, Dict, TypedDict

from langgraph.graph import END, START, StateGraph

from agent_a1_caa_hub import get_langgraph_node as node_a1
from agent_a2_cca_hub import get_langgraph_node as node_a2
from agent_a3_cda_hub import get_langgraph_node as node_a3
from agent_a4_discharge_parser import get_langgraph_node as node_a4
from agent_a5_baseline_compare import get_langgraph_node as node_a5
from agent_a6_task_pack_agent import get_langgraph_node as node_a6
from agent_a7_event_structuring_agent import get_langgraph_node as node_a7
from agent_a8_escalation_decision_agent import get_langgraph_node as node_a8
from agent_a9_nursing_assessment_agent import get_langgraph_node as node_a9
from agent_a10_trend_comparison_agent import get_langgraph_node as node_a10
from agent_a11_weekly_summary_agent import get_langgraph_node as node_a11
from agent_a12_consult_agent import get_langgraph_node as node_a12
from agent_a13_outcome_report_agent import get_langgraph_node as node_a13
from agent_a14_audit_eval_agent import get_langgraph_node as node_a14
from common_utils import DEFAULT_CONFIG_PATH, DEFAULT_GRAPH_PATH


class TaskAgentState(TypedDict, total=False):
    graph_path: str
    config_path: str
    use_tools: bool
    a1_input: str
    a2_input: str
    a3_input: str
    a4_input: str
    a5_input: str
    a6_input: str
    a7_input: str
    a8_input: str
    a9_input: str
    a10_input: str
    a11_input: str
    a12_input: str
    a13_input: str
    a14_input: str
    a1_output: Dict[str, Any]
    a2_output: Dict[str, Any]
    a3_output: Dict[str, Any]
    a4_output: Dict[str, Any]
    a5_output: Dict[str, Any]
    a6_output: Dict[str, Any]
    a7_output: Dict[str, Any]
    a8_output: Dict[str, Any]
    a9_output: Dict[str, Any]
    a10_output: Dict[str, Any]
    a11_output: Dict[str, Any]
    a12_output: Dict[str, Any]
    a13_output: Dict[str, Any]
    a14_output: Dict[str, Any]


def create_workflow():
    workflow = StateGraph(TaskAgentState)
    workflow.add_node("a1", node_a1())
    workflow.add_node("a2", node_a2())
    workflow.add_node("a3", node_a3())
    workflow.add_node("a4", node_a4())
    workflow.add_node("a5", node_a5())
    workflow.add_node("a6", node_a6())
    workflow.add_node("a7", node_a7())
    workflow.add_node("a8", node_a8())
    workflow.add_node("a9", node_a9())
    workflow.add_node("a10", node_a10())
    workflow.add_node("a11", node_a11())
    workflow.add_node("a12", node_a12())
    workflow.add_node("a13", node_a13())
    workflow.add_node("a14", node_a14())
    workflow.add_edge(START, "a1")
    workflow.add_edge("a1", "a2")
    workflow.add_edge("a2", "a3")
    workflow.add_edge("a3", "a4")
    workflow.add_edge("a4", "a5")
    workflow.add_edge("a5", "a6")
    workflow.add_edge("a6", "a7")
    workflow.add_edge("a7", "a8")
    workflow.add_edge("a8", "a9")
    workflow.add_edge("a9", "a10")
    workflow.add_edge("a10", "a11")
    workflow.add_edge("a11", "a12")
    workflow.add_edge("a12", "a13")
    workflow.add_edge("a13", "a14")
    workflow.add_edge("a14", END)
    return workflow.compile()


if __name__ == "__main__":
    app = create_workflow()
    state: TaskAgentState = {
        "graph_path": str(DEFAULT_GRAPH_PATH),
        "config_path": str(DEFAULT_CONFIG_PATH),
        "use_tools": True,
    }
    result = app.invoke(state)
    print("workflow done", list(result.keys()))
