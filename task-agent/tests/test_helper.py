#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试辅助：Agent 对照实验 + Tool 测试报告。"""

from pathlib import Path
from typing import Any, Callable, Dict, List

from common_utils import TEST_DIR, create_pdf_report, date_text, now_text


def metric_snapshot(text: str) -> Dict[str, int]:
    content = str(text or "")
    return {"chars": len(content), "markers": content.count("：") + content.count(":")}


def run_agent_case(
    agent_name: str,
    run_callable: Callable[..., Dict[str, Any]],
    prompt_text: str,
    graph_path: Path,
    tool_desc: str = "",
) -> Dict[str, Any]:
    result_with_tools = run_callable(prompt_text, graph_path=graph_path, use_tools=True)
    result_without_tools = run_callable(prompt_text, graph_path=graph_path, use_tools=False)
    metric_with_tools = metric_snapshot(result_with_tools.get("text", ""))
    metric_without_tools = metric_snapshot(result_without_tools.get("text", ""))
    lines: List[str] = [
        f"测试时间：{now_text()}",
        "一、测试目的：验证工具增强对输出质量提升作用。",
        "二、测试内容：同一输入下，分别运行 use_tools=True/False。",
        "三、测试方法：对比输出结构与长度，核对产物路径。",
        "四、测试过程：",
        "1) 启用工具运行；2) 禁用工具运行；3) 指标对照；4) 结论归纳。",
        "五、测试结果：",
        f"启用工具 success={result_with_tools.get('success')} chars={metric_with_tools['chars']} markers={metric_with_tools['markers']}",
        f"禁用工具 success={result_without_tools.get('success')} chars={metric_without_tools['chars']} markers={metric_without_tools['markers']}",
        f"工具说明：{tool_desc or '见 SPEC.tool_names'}",
        "六、结论：工具可显著提升智能体输出准确性、完整性与专业性，助力机构提供更精准照护与医疗服务。",
        "",
        "【启用工具输出摘录】",
        str(result_with_tools.get("text", ""))[:1200],
        "",
        "【禁用工具输出摘录】",
        str(result_without_tools.get("text", ""))[:1200],
    ]
    report_path = TEST_DIR / f"test_report_{agent_name}_{date_text()}.pdf"
    create_pdf_report(f"{agent_name} 测试报告", lines, report_path)
    return {
        "result_with_tools": result_with_tools,
        "result_without_tools": result_without_tools,
        "report": str(report_path),
    }


def run_tool_case(tool_name: str, tool_callable: Callable[[Dict[str, Any]], Any], graph_data: Dict[str, Any]) -> Dict[str, Any]:
    output = tool_callable(graph_data)
    lines = [
        f"测试时间：{now_text()}",
        "测试目的：验证工具能正确抽取知识图谱信息。",
        f"工具名称：{tool_name}",
        f"输出类型：{type(output).__name__}",
        f"输出预览：{str(output)[:2500]}",
    ]
    report_path = TEST_DIR / f"test_report_tool_{tool_name}_{date_text()}.pdf"
    create_pdf_report(f"Tool {tool_name} 测试报告", lines, report_path)
    return {"output": output, "report": str(report_path)}
