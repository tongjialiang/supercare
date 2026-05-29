#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A9 护士评估支撑智能体（双文件输出）。"""

import json
from pathlib import Path
from typing import Any, Callable, Dict

from common_utils import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_GRAPH_PATH,
    REPORT_MAX_CHARS,
    TOOL_PURPOSE,
    TOOL_REGISTRY,
    AgentSpec,
    StructuredAgentLogger,
    TaskAgentRunner,
    build_agent_node,
    build_output_path,
    clamp_text,
    extract_tag_content,
    sanitize_document_body,
    write_report_outputs,
    invoke_qwen_with_retry,
    load_graph,
    parse_thinking_and_body,
)

SPEC = AgentSpec(
    agent_code="A9",
    agent_name="Nursing_Assessment_Agent",
    target_user="护士评估",
    duty="输出《护士评估结论与调整建议》与《照护员周重点任务》。",
    input_desc="NPI/ADL/进食/睡眠等信息",
    output_desc="双PDF",
    tool_names=["tool_照护洞察", "tool_个性化健康档案", "tool_体征洞察", "tool_用药洞察", "tool_健康评估记录", "tool_睡眠记录"],
    execution_rules=["优先最新输入", "无依据留空", "正文不限制字数"],
)
PROMPT_RUNNER = TaskAgentRunner(SPEC)


def run_agent(user_input: str, graph_path: Path | None = None, use_tools: bool = True) -> Dict[str, Any]:
    graph = load_graph(graph_path or DEFAULT_GRAPH_PATH)
    tools: Dict[str, Any] = {}
    timeline = []
    if use_tools:
        for tool_name in SPEC.tool_names:
            tools[tool_name] = TOOL_REGISTRY[tool_name](graph)
            timeline.append({"工具名称": tool_name, "调用时机": "LLM前", "作用": TOOL_PURPOSE.get(tool_name, "")})
    else:
        timeline.append({"工具名称": "无", "调用时机": "对照实验", "作用": "禁用工具"})
    system_prompt = (
        PROMPT_RUNNER.build_system_prompt()
        + "\n必须输出：<思考>...</思考><护士评估正文>...</护士评估正文><周任务正文>...</周任务正文>\n"
        + "《护士评估结论与调整建议》字段：NPI结论、ADL结论、进食评估结论、睡眠评估结论、当前风险判断、护理员调整建议、是否需要GP介入、是否更新护理员任务、护理员判断依据、视频规程链接、家属沟通建议。\n"
        + "《照护员周重点任务》字段：评估日期、评估类型、NPI结论、ADL结论、进食评估结论、睡眠评估结论、当前风险判断、护理员调整建议、是否需要GP介入、是否更新护理员任务、护理员判断依据、视频规程链接、家属沟通建议。"
    )
    user_prompt = "【最新实时信息】\n" + user_input + "\n\n【历史参考】\n" + (json.dumps(tools, ensure_ascii=False, indent=2) if tools else "（未使用工具）")
    logger = StructuredAgentLogger("A9", "Nursing_Assessment_Agent")
    steps = ["读取图谱", "工具抽取", "调用LLM", "解析双正文", "输出双PDF"]
    try:
        raw = invoke_qwen_with_retry(
            system_prompt,
            user_prompt,
            DEFAULT_CONFIG_PATH,
            required_tags=["思考", "护士评估正文", "周任务正文"],
            max_retry=1,
        )
        thinking = extract_tag_content(raw, "思考")
        body_a = clamp_text(sanitize_document_body(extract_tag_content(raw, "护士评估正文")), REPORT_MAX_CHARS)
        body_b = clamp_text(sanitize_document_body(extract_tag_content(raw, "周任务正文")), REPORT_MAX_CHARS)
        # 兜底：若模型未按自定义标签返回，则回退到通用正文，避免产出空文档。
        if not body_a or not body_b:
            _, fallback_body = parse_thinking_and_body(raw)
            fallback_body = clamp_text(fallback_body, REPORT_MAX_CHARS)
            if not body_a:
                body_a = fallback_body
            if not body_b:
                body_b = fallback_body
        path_a_pdf, path_a_md = write_report_outputs("护士评估结论与调整建议", body_a, "A9", "护士评估结论与调整建议")
        path_b_pdf, path_b_md = write_report_outputs("照护员周重点任务", body_b, "A9", "照护员周重点任务")
        logger.log(user_input[:500], steps, timeline, tools, thinking, f"{path_a_pdf.name},{path_b_pdf.name}", "success")
        return {
            "success": True,
            "thinking": thinking,
            "text": body_a + "\n---\n" + body_b,
            "pdf_paths": [str(path_a_pdf), str(path_b_pdf)],
            "md_paths": [str(path_a_md), str(path_b_md)],
            "use_tools": use_tools,
        }
    except Exception as exc:
        logger.log(user_input[:500], steps, timeline, tools, "", "失败", "failed", str(exc))
        return {"success": False, "error": str(exc), "use_tools": use_tools}


def get_langgraph_node(input_key: str = "a9_input", output_key: str = "a9_output") -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def node(state: Dict[str, Any]) -> Dict[str, Any]:
        use_tools = state.get("use_tools", True)
        if isinstance(use_tools, str):
            use_tools = use_tools.lower() not in ("0", "false", "no")
        result = run_agent(
            user_input=str(state.get(input_key, "")),
            graph_path=Path(str(state.get("graph_path", DEFAULT_GRAPH_PATH))),
            use_tools=bool(use_tools),
        )
        return {**state, output_key: result}

    return node
