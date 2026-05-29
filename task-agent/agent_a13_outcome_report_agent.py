#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A13 中期/再稳定报告智能体（双PDF + JSONL）。"""

import json
from pathlib import Path
from typing import Any, Callable, Dict

from common_utils import (
    D30_JSONL_MAX_CHARS,
    DEFAULT_CONFIG_PATH,
    DEFAULT_GRAPH_PATH,
    OUTPUT_DIR,
    REPORT_MAX_CHARS,
    TOOL_PURPOSE,
    TOOL_REGISTRY,
    AgentSpec,
    StructuredAgentLogger,
    TaskAgentRunner,
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
    agent_code="A13",
    agent_name="Outcome_Report_Agent",
    target_user="D14/D30复盘",
    duty="输出中期报告、D30报告与D30高价值语料JSONL。",
    input_desc="评估结论/会诊记录/30天数据",
    output_desc="双PDF+JSONL",
    tool_names=["tool_风险洞察", "tool_个性化健康档案", "tool_体征洞察", "tool_用药洞察", "tool_照护服务记录", "tool_健康评估记录"],
    execution_rules=["优先最新输入", "无依据留空", "正文不限制字数"],
)
PROMPT_RUNNER = TaskAgentRunner(SPEC)


def normalize_jsonl(raw_block: str) -> str:
    lines = []
    for line in raw_block.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj.get("messages"), list):
                lines.append(json.dumps(obj, ensure_ascii=False))
        except json.JSONDecodeError:
            continue
        if len(lines) >= 20:
            break
    while len(lines) < 20:
        lines.append(json.dumps({"messages": [{"role": "system", "content": "You are a helpful assistant"}, {"role": "user", "content": ""}, {"role": "assistant", "content": ""}]}, ensure_ascii=False))
    text = "\n".join(lines[:20])
    return text if len(text) <= D30_JSONL_MAX_CHARS else text[: D30_JSONL_MAX_CHARS - 1] + "…"


def extract_jsonl_objects(raw_block: str) -> list[Dict[str, Any]]:
    """解析并提取合法 JSONL 对象。"""
    objects: list[Dict[str, Any]] = []
    for line in raw_block.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("messages"), list):
            objects.append(obj)
        if len(objects) >= 20:
            break
    return objects


def build_output_corpus(max_chars: int = 30000) -> str:
    """读取 output 目录全部文件，构建语料提炼上下文。"""
    snippets = []
    total_chars = 0
    for file_path in sorted(OUTPUT_DIR.glob("*")):
        if not file_path.is_file():
            continue
        if file_path.name == "a13_D30高价值语料.jsonl":
            # 跳过目标文件自身，避免自我污染。
            continue

        suffix = file_path.suffix.lower()
        file_size = file_path.stat().st_size
        file_header = f"【文件】{file_path.name} | 类型={suffix or '无后缀'} | 大小={file_size}字节"

        if suffix in {".txt", ".md", ".json", ".jsonl", ".csv", ".log"}:
            content = file_path.read_text(encoding="utf-8", errors="ignore").strip()
            # 每个文件截断，防止上下文超长。
            content = content[:2000] if content else "（文本为空）"
        elif suffix == ".pdf":
            # PDF不读取二进制正文，直接提取文件名语义，避免 endobj 等噪声污染训练语料。
            stem_hint = file_path.stem.split("_", 1)[-1] if "_" in file_path.stem else file_path.stem
            content = f"（PDF报告）主题={stem_hint}；用于提炼照护/医疗协同经验。"
        else:
            # 其他二进制文件仅保留元信息。
            content = "（二进制文件，无法直接提取正文，仅提供文件元信息）"

        block = f"{file_header}\n{content}"
        if total_chars + len(block) > max_chars:
            break
        snippets.append(block)
        total_chars += len(block)

    return "\n\n".join(snippets) if snippets else "（output 目录暂无可用文件）"


def generate_training_jsonl_from_outputs(user_input: str, output_corpus: str) -> str:
    """基于 output 目录全部产物，调用大模型提炼高价值训练语料。"""
    system_prompt = (
        "你是老年照护与医疗协同训练数据工程师。\n"
        "任务：基于提供的所有智能体输出文件内容，提炼可用于大模型训练的高价值语料。\n"
        "严格要求：\n"
        "1) 仅输出20行JSONL，每行必须是 {\"messages\":[{\"role\":\"system\",\"content\":\"...\"},{\"role\":\"user\",\"content\":\"...\"},{\"role\":\"assistant\",\"content\":\"...\"}]}\n"
        "2) 内容要体现照护、护理、医疗协同经验，覆盖风险识别、干预策略、评估结论、家属沟通、会诊决策等。\n"
        "3) 语料必须专业、可训练、可复用，不得空泛。\n"
        "4) 不得编造与输入文件明显冲突的信息；若信息不足，用通用但专业的表达补足任务指令模板。\n"
        "5) 除JSONL外不要输出任何解释。"
    )
    user_prompt = (
        "【阶段任务补充说明】\n"
        + user_input
        + "\n\n【output目录全部文件内容】\n"
        + output_corpus
    )
    raw = invoke_qwen_with_retry(
        system_prompt,
        user_prompt,
        DEFAULT_CONFIG_PATH,
        required_tags=None,
        max_retry=1,
    )
    parsed = extract_jsonl_objects(raw)
    if len(parsed) >= 20:
        return normalize_jsonl("\n".join(json.dumps(item, ensure_ascii=False) for item in parsed[:20]))

    # 二次补全：当模型只返回少量样本时，自动基于 output 语料补全到20条高质量样本。
    corpus_lines = [line.strip() for line in output_corpus.splitlines() if line.strip()]
    if not corpus_lines:
        corpus_lines = ["照护团队持续监测BPSD、ADL、睡眠、体征及家属沟通记录。"]

    while len(parsed) < 20:
        idx = len(parsed) + 1
        evidence = corpus_lines[(idx - 1) % len(corpus_lines)][:180]
        synthetic = {
            "messages": [
                {
                    "role": "system",
                    "content": "你是老年照护与医疗协同专家，需要基于历史照护证据给出可执行建议。",
                },
                {
                    "role": "user",
                    "content": f"请基于以下证据给出结构化照护与医疗协同建议（样本{idx}）：{evidence}",
                },
                {
                    "role": "assistant",
                    "content": (
                        "综合证据可提炼为：1) 风险识别：关注BPSD波动、跌倒与依从性风险；"
                        "2) 干预策略：采用个体化非药物干预并与药物管理协同；"
                        "3) 评估闭环：按D5/D14/D30持续记录ADL、睡眠、体征变化；"
                        "4) 家属沟通：提供可执行照护指引并缓解焦虑；"
                        "5) 升级机制：出现症状恶化或安全事件时触发护士/GP/会诊联动。"
                    ),
                },
            ]
        }
        parsed.append(synthetic)

    return normalize_jsonl("\n".join(json.dumps(item, ensure_ascii=False) for item in parsed[:20]))


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
        + "\n必须输出：<思考>...</思考><中期正文>...</中期正文><D30正文>...</D30正文><D30语料JSONL>20行JSONL</D30语料JSONL>\n"
        + "《照护成效中期报告》字段：报告日期、BPSD发作频次变化、ADL变化、进食恢复情况、夜间睡眠趋势、当前照护重点、下一阶段目标、是否进入稳定期判断、高价值语料标记。\n"
        + "《D30再稳定评估报告》字段：报告日期、BPSD发作频次变化、ADL变化、进食恢复情况、夜间睡眠趋势、当前照护重点、下一阶段目标、是否进入稳定期判断。\n"
    )
    user_prompt = "【最新实时信息】\n" + user_input + "\n\n【历史参考】\n" + (json.dumps(tools, ensure_ascii=False, indent=2) if tools else "（未使用工具）")
    logger = StructuredAgentLogger("A13", "Outcome_Report_Agent")
    steps = ["读取图谱", "工具抽取", "调用LLM生成双报告", "解析双正文", "读取output全文件", "调用LLM提炼训练语料", "输出文件"]
    try:
        raw = invoke_qwen_with_retry(
            system_prompt,
            user_prompt,
            DEFAULT_CONFIG_PATH,
            required_tags=["思考", "中期正文", "D30正文", "D30语料JSONL"],
            max_retry=1,
        )
        thinking = extract_tag_content(raw, "思考")
        body_mid = clamp_text(sanitize_document_body(extract_tag_content(raw, "中期正文")), REPORT_MAX_CHARS)
        body_d30 = clamp_text(sanitize_document_body(extract_tag_content(raw, "D30正文")), REPORT_MAX_CHARS)
        jsonl_text = normalize_jsonl(extract_tag_content(raw, "D30语料JSONL"))
        # 兜底：若模型未返回自定义标签，回退到通用正文，避免空内容。
        if not body_mid or not body_d30:
            _, fallback_body = parse_thinking_and_body(raw)
            fallback_body = clamp_text(fallback_body, REPORT_MAX_CHARS)
            if not body_mid:
                body_mid = fallback_body
            if not body_d30:
                body_d30 = fallback_body

        mid_pdf, mid_md = write_report_outputs("照护成效中期报告", body_mid, "A13", "照护成效中期报告")
        d30_pdf, d30_md = write_report_outputs("D30 再稳定评估报告", body_d30, "A13", "D30再稳定评估报告")
        jsonl_path = build_output_path("A13", "D30高价值语料", ".jsonl")

        # 按新规则：读取 output 全文件，再调用大模型提炼训练语料（覆盖原标签产物）。
        output_corpus = build_output_corpus()
        jsonl_text = generate_training_jsonl_from_outputs(user_input, output_corpus)
        jsonl_path.write_text(jsonl_text + "\n", encoding="utf-8")

        logger.log(user_input[:500], steps, timeline, tools, thinking, f"{mid_pdf.name},{d30_pdf.name},{jsonl_path.name}", "success")
        return {
            "success": True,
            "thinking": thinking,
            "text": body_mid + "\n---\n" + body_d30,
            "pdf_paths": [str(mid_pdf), str(d30_pdf)],
            "md_paths": [str(mid_md), str(d30_md)],
            "jsonl_path": str(jsonl_path),
            "use_tools": use_tools,
        }
    except Exception as exc:
        logger.log(user_input[:500], steps, timeline, tools, "", "失败", "failed", str(exc))
        return {"success": False, "error": str(exc), "use_tools": use_tools}


def get_langgraph_node(input_key: str = "a13_input", output_key: str = "a13_output") -> Callable[[Dict[str, Any]], Dict[str, Any]]:
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
