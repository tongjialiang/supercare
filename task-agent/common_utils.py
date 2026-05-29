#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TaskAgent 公共能力：工具、日志、LLM调用、PDF输出、节点封装。"""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from openai import OpenAI
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path("/srv/supercare/task-agent")
LOG_DIR = PROJECT_ROOT / "logs"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEST_DIR = PROJECT_ROOT / "tests"

DEFAULT_CONFIG_PATH = Path("/srv/supercare/config/data_agent1_config.json")
DEFAULT_GRAPH_PATH = Path(
    "/srv/supercare/data-agent1/ms_chen_CareCase/results/ms_chen_CareCase_elder_health_computing_graph.json"
)

ALLOWED_TYPES = [
    "老人主体",
    "近况摘要",
    "风险洞察",
    "照护洞察",
    "个性化健康档案",
    "基础信息",
    "体征洞察",
    "用药洞察",
    "照护服务记录",
    "健康评估记录",
    "睡眠记录",
]
TIME_TYPES = {"体征洞察", "用药洞察", "照护服务记录", "健康评估记录", "睡眠记录"}

REPORT_MAX_CHARS = 0
D30_JSONL_MAX_CHARS = 5000


def ensure_dirs() -> None:
    """确保目录存在。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DIR.mkdir(parents=True, exist_ok=True)


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def date_text() -> str:
    return datetime.now().strftime("%Y%m%d")


def safe_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_output_path(agent_code: str, output_name: str, extension: str = ".pdf") -> Path:
    """输出命名：a{数字}_{文件名}.ext"""
    code_upper = safe_text(agent_code).upper()
    suffix = code_upper[1:] if code_upper.startswith("A") else code_upper
    prefix = f"a{suffix}"
    clean_name = safe_text(output_name).replace("/", "_").replace("\\", "_").replace("《", "").replace("》", "")
    ext = extension if extension.startswith(".") else f".{extension}"
    return OUTPUT_DIR / f"{prefix}_{clean_name}{ext}"


def parse_time(value: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(safe_text(value), fmt)
        except ValueError:
            continue
    return datetime.min


def extract_timestamp(node_item: Dict[str, Any]) -> str:
    properties = node_item.get("properties", {})
    if not isinstance(properties, dict):
        return ""
    for key in ["timestamp", "时间", "时间戳", "记录时间", "日期", "发生时间", "评估时间", "用药时间"]:
        if safe_text(properties.get(key)):
            return safe_text(properties.get(key))
    fields = properties.get("fields", {})
    if isinstance(fields, dict):
        for key in ["时间", "时间戳", "记录时间", "日期", "发生时间"]:
            if safe_text(fields.get(key)):
                return safe_text(fields.get(key))
    return ""


def node_brief(node_item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": node_item.get("id", ""),
        "type": node_item.get("type", ""),
        "name": node_item.get("name", ""),
        "timestamp": extract_timestamp(node_item),
        "properties": node_item.get("properties", {}),
    }


def load_graph(graph_path: Optional[Path] = None) -> Dict[str, Any]:
    return load_json(graph_path or DEFAULT_GRAPH_PATH)


def select_nodes_by_type(graph_data: Dict[str, Any], type_name: str, min_count: int = 5, max_count: int = 10) -> List[Dict[str, Any]]:
    nodes = [node for node in graph_data.get("nodes", []) if node.get("type") == type_name]
    if type_name in TIME_TYPES:
        nodes = sorted(nodes, key=lambda item: parse_time(extract_timestamp(item)), reverse=True)
    else:
        nodes = sorted(nodes, key=lambda item: safe_text(item.get("name", "")))
    return nodes[:max_count] if len(nodes) > max_count else nodes


def tool_老人主体(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "老人主体", 1, 2)]


def tool_近况摘要(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "近况摘要")]


def tool_风险洞察(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "风险洞察")]


def tool_照护洞察(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "照护洞察")]


def tool_个性化健康档案(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "个性化健康档案")]


def tool_基础信息(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "基础信息")]


def tool_体征洞察(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "体征洞察")]


def tool_用药洞察(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "用药洞察")]


def tool_照护服务记录(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "照护服务记录")]


def tool_健康评估记录(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "健康评估记录")]


def tool_睡眠记录(graph_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [node_brief(item) for item in select_nodes_by_type(graph_data, "睡眠记录")]


def tool_最新时序摘要(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "体征洞察": tool_体征洞察(graph_data),
        "用药洞察": tool_用药洞察(graph_data),
        "照护服务记录": tool_照护服务记录(graph_data),
        "健康评估记录": tool_健康评估记录(graph_data),
        "睡眠记录": tool_睡眠记录(graph_data),
    }


def tool_风险照护联动(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    return {"风险洞察": tool_风险洞察(graph_data), "照护洞察": tool_照护洞察(graph_data), "近况摘要": tool_近况摘要(graph_data)}


def tool_任务决策摘要(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "老人主体": tool_老人主体(graph_data),
        "个性化健康档案": tool_个性化健康档案(graph_data),
        "风险洞察": tool_风险洞察(graph_data),
        "照护服务记录": tool_照护服务记录(graph_data),
    }


def tool_疾病分期洞察(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    """本地序贯疾病分期：从 A0 流水线缓存读取，供超级 GP 分层照护。"""
    from staging.staging_cache import load_staging_bundle

    bundle = load_staging_bundle()
    staging = bundle.get("staging", bundle.get("sustain", {}))
    focus = staging.get("focus_case_staging") or {}
    return {
        "模型说明": staging.get("model", ""),
        "运行方式": staging.get("runtime", "本地 A0 流水线"),
        "焦点病例分期": focus,
        "GP照护分层建议": staging.get("gp_care_implications", {}),
        "队列病例数": staging.get("cohort_size", 0),
        "生物标志物Excel": bundle.get("excel_path", ""),
    }


def tool_贝叶斯风险后验(graph_data: Dict[str, Any]) -> Dict[str, Any]:
    """贝叶斯融合：在分期先验上更新 BPSD/跌倒/照护强度后验概率。"""
    from staging.staging_cache import load_staging_bundle

    bundle = load_staging_bundle()
    bayesian = bundle.get("bayesian", {})
    return {
        "模型说明": bayesian.get("model", ""),
        "先验": bayesian.get("priors", {}),
        "似然更新项": bayesian.get("likelihood_updates", []),
        "后验概率": bayesian.get("posteriors", {}),
        "决策阈值": bayesian.get("decision_thresholds", {}),
        "GP建议动作": bayesian.get("gp_actions", []),
    }


TOOL_REGISTRY: Dict[str, Callable[[Dict[str, Any]], Any]] = {
    "tool_老人主体": tool_老人主体,
    "tool_近况摘要": tool_近况摘要,
    "tool_风险洞察": tool_风险洞察,
    "tool_照护洞察": tool_照护洞察,
    "tool_个性化健康档案": tool_个性化健康档案,
    "tool_基础信息": tool_基础信息,
    "tool_体征洞察": tool_体征洞察,
    "tool_用药洞察": tool_用药洞察,
    "tool_照护服务记录": tool_照护服务记录,
    "tool_健康评估记录": tool_健康评估记录,
    "tool_睡眠记录": tool_睡眠记录,
    "tool_最新时序摘要": tool_最新时序摘要,
    "tool_风险照护联动": tool_风险照护联动,
    "tool_任务决策摘要": tool_任务决策摘要,
    "tool_疾病分期洞察": tool_疾病分期洞察,
    "tool_贝叶斯风险后验": tool_贝叶斯风险后验,
}

TOOL_PURPOSE = {name: f"{name}：从长者智能计算图提取历史参考证据" for name in TOOL_REGISTRY}
TOOL_PURPOSE["tool_疾病分期洞察"] = "tool_疾病分期洞察：本地序贯疾病分期与 GP 分层照护建议（A0 本地计算）"
TOOL_PURPOSE["tool_贝叶斯风险后验"] = "tool_贝叶斯风险后验：贝叶斯后验概率与升级决策阈值（A0 计算）"


def extract_tag_content(raw_text: str, tag_name: str) -> str:
    pattern = rf"<{tag_name}>([\s\S]*?)</{tag_name}>"
    match = re.search(pattern, raw_text)
    return safe_text(match.group(1)) if match else ""


def clamp_text(content: str, max_chars: int) -> str:
    if max_chars <= 0:
        return content
    return content if len(content) <= max_chars else content[: max_chars - 1] + "…"


def sanitize_document_body(body: str) -> str:
    """清洗正文：去除思维链标签、正文标题标记及多余空行。"""
    content = safe_text(body)
    if not content:
        return ""
    # 完整思维链块
    content = re.sub(r"<思考>[\s\S]*?</思考>", "", content)
    # 未闭合思维链：丢弃 <思考> 至 <正文> 或文档标题之前的内容
    if "<思考>" in content:
        if "<正文>" in content:
            content = content.split("<正文>", 1)[-1]
        elif "</思考>" in content:
            content = content.split("</思考>", 1)[-1]
        else:
            content = re.sub(r"^<思考>[\s\S]*?(?=\n# |\n\*\*[^*]+\*\*)", "", content, count=1)
            content = re.sub(r"^<思考>[\s\S]*$", "", content, count=1)
    content = re.sub(r"</?正文>", "", content)
    content = re.sub(r"^【正文[^】]*】\s*", "", content.strip())
    content = re.sub(r"^【深度思考[^】]*】[\s\S]*?(?=\n# |\n\*\*|\Z)", "", content, count=1)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def parse_thinking_and_body(raw_text: str) -> Tuple[str, str]:
    thinking = extract_tag_content(raw_text, "思考")
    body = extract_tag_content(raw_text, "正文")
    if not body:
        body = safe_text(raw_text)
    if thinking and thinking in body:
        body = body.replace(f"<思考>{thinking}</思考>", "")
    body = sanitize_document_body(body)
    return thinking, clamp_text(body, REPORT_MAX_CHARS)


def build_pdf_lines(body: str) -> List[str]:
    """组装 PDF 正文行：仅输出可用文档内容，不含思维链与「正文」标题。"""
    content = safe_text(body)
    if not content:
        return ["（暂无内容）"]
    return content.splitlines()


def create_pdf_report(title: str, body_lines: List[str], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    pdf_canvas = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    def wrap_line(line: str, width_chars: int = 42) -> List[str]:
        text = safe_text(line).replace("\t", "    ")
        if not text:
            return [""]
        wrapped: List[str] = []
        for paragraph in text.splitlines() or [text]:
            wrapped.extend(textwrap.wrap(paragraph, width=width_chars, break_long_words=True, break_on_hyphens=False) or [""])
        return wrapped

    pdf_canvas.setFillColorRGB(0.95, 0.97, 1.0)
    pdf_canvas.rect(36, height - 86, width - 72, 42, fill=1, stroke=0)
    pdf_canvas.setFillColorRGB(0.08, 0.16, 0.32)
    pdf_canvas.setFont("STSong-Light", 16)
    pdf_canvas.drawString(48, height - 70, title[:80])
    pdf_canvas.setFillColorRGB(0.2, 0.2, 0.2)
    pdf_canvas.setFont("STSong-Light", 10)
    pdf_canvas.drawString(48, height - 84, f"生成时间：{now_text()}")

    pdf_canvas.setFillColorRGB(0, 0, 0)
    pdf_canvas.setFont("STSong-Light", 11)
    y_axis = height - 110
    line_height = 16
    for raw_line in body_lines:
        for wrapped_line in wrap_line(raw_line):
            if y_axis < 52:
                pdf_canvas.showPage()
                pdf_canvas.setFont("STSong-Light", 11)
                y_axis = height - 52
            pdf_canvas.drawString(48, y_axis, wrapped_line)
            y_axis -= line_height
        y_axis -= 4

    pdf_canvas.save()
    return output_path


def create_markdown_report(body: str, output_path: Path) -> Path:
    """写入 Markdown 报告：仅正文，不含来源/转换时间等元数据。"""
    content = sanitize_document_body(safe_text(body)) or "（暂无内容）"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content + "\n", encoding="utf-8")
    return output_path


def write_report_outputs(title: str, body: str, agent_code: str, file_stem: str) -> Tuple[Path, Path]:
    """同时生成 PDF 与 Markdown 产物。"""
    stem = safe_text(file_stem)
    pdf_path = build_output_path(agent_code, stem, ".pdf")
    md_path = build_output_path(agent_code, stem, ".md")
    create_pdf_report(title, build_pdf_lines(body), pdf_path)
    create_markdown_report(body, md_path)
    return pdf_path, md_path


class StructuredAgentLogger:
    """结构化日志。"""

    def __init__(self, agent_code: str, agent_name: str) -> None:
        ensure_dirs()
        self.log_path = LOG_DIR / f"{agent_name}_log_{date_text()}.log"
        self.agent_code = agent_code
        self.agent_name = agent_name

    def log(
        self,
        input_summary: str,
        steps: List[str],
        tool_timeline: List[Dict[str, str]],
        tool_details: Dict[str, Any],
        thinking_text: str,
        output_summary: str,
        status: str,
        exception_text: str = "",
    ) -> None:
        payload = {
            "调用时间": now_text(),
            "Agent编号": self.agent_code,
            "Agent名称": self.agent_name,
            "输入摘要": input_summary,
            "执行步骤": steps,
            "工具调用流水": tool_timeline,
            "工具调用详情": tool_details,
            "思维链_完整推理": thinking_text,
            "输出摘要": output_summary,
            "异常信息": exception_text,
            "执行状态": status,
        }
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_qwen_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    content = load_json(config_path)
    qwen = content.get("qwen", {})
    return {
        "api_key": qwen.get("api_key", ""),
        "base_url": qwen.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "model": qwen.get("model", "qwen3-max"),
        "max_tokens": int(qwen.get("max_tokens", 4096)),
        "temperature": float(qwen.get("temperature", 0.2)),
    }


def invoke_qwen(system_prompt: str, user_prompt: str, config_path: Path = DEFAULT_CONFIG_PATH) -> str:
    config = load_qwen_config(config_path)
    if not safe_text(config["api_key"]):
        return "<思考>未配置API Key。</思考><正文></正文>"
    client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
    response = client.chat.completions.create(
        model=config["model"],
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
    )
    return safe_text(response.choices[0].message.content)


def is_output_incomplete(raw_text: str, required_tags: Optional[List[str]] = None) -> bool:
    """检测输出是否疑似截断或标签未闭合。"""
    text = safe_text(raw_text)
    if not text:
        return True
    if text.endswith("<") or text.endswith("</") or text.endswith("```"):
        return True

    tags = required_tags or []
    for tag in tags:
        open_tag = f"<{tag}>"
        close_tag = f"</{tag}>"
        open_count = text.count(open_tag)
        close_count = text.count(close_tag)
        if open_count != close_count:
            return True
        if open_count > 0 and close_count == 0:
            return True
    return False


def invoke_qwen_with_retry(
    system_prompt: str,
    user_prompt: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
    required_tags: Optional[List[str]] = None,
    max_retry: int = 1,
) -> str:
    """调用Qwen并在疑似截断时自动重试。"""
    final_prompt = user_prompt
    for attempt in range(max_retry + 1):
        raw_text = invoke_qwen(system_prompt, final_prompt, config_path=config_path)
        if not is_output_incomplete(raw_text, required_tags=required_tags):
            return raw_text
        if attempt < max_retry:
            final_prompt = (
                user_prompt
                + "\n\n【补充要求】你上一次输出疑似被截断。请从头完整重写，"
                "确保所有标签闭合，结尾为完整句，不要输出半截内容。"
            )
    return raw_text


GLOBAL_PROMPT_RULES = """
【数据来源规则】
1) 用户输入是当前决策核心依据（最新实时信息）。
2) 工具抽取的图谱信息仅是历史参考，不得覆盖用户输入。
3) 无法可靠推出的字段必须留空，不得编造。

【输出格式规则】
必须输出：
<思考>完整推理过程</思考>
<正文>报告正文（不限制字数）</正文>
"""


@dataclass
class AgentSpec:
    agent_code: str
    agent_name: str
    target_user: str
    duty: str
    input_desc: str
    output_desc: str
    tool_names: List[str]
    execution_rules: List[str]
    output_mode: str = "pdf"
    pdf_title: str = ""
    output_file_stem: str = ""
    report_dimensions: str = ""


class TaskAgentRunner:
    """单智能体运行器。"""

    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec
        self.logger = StructuredAgentLogger(spec.agent_code, spec.agent_name)

    def build_system_prompt(self) -> str:
        tool_lines = [f"- {name}：{TOOL_PURPOSE.get(name, '')}" for name in self.spec.tool_names]
        rule_lines = [f"- {rule}" for rule in self.spec.execution_rules]
        return (
            f"【智能体名称】{self.spec.agent_name}\n"
            f"【主要服务对象】{self.spec.target_user}\n"
            f"【核心职责】{self.spec.duty}\n"
            f"【关键输入】{self.spec.input_desc}\n"
            f"【关键输出】{self.spec.output_desc}\n"
            f"【可调用工具】\n" + "\n".join(tool_lines) + "\n"
            f"【执行规则】\n" + "\n".join(rule_lines) + "\n"
            f"【文档维度要求】{self.spec.report_dimensions}\n"
            + GLOBAL_PROMPT_RULES
        )

    def run(
        self,
        user_input: str,
        graph_path: Path = DEFAULT_GRAPH_PATH,
        config_path: Path = DEFAULT_CONFIG_PATH,
        use_tools: bool = True,
    ) -> Dict[str, Any]:
        graph_data = load_graph(graph_path)
        tool_details: Dict[str, Any] = {}
        tool_timeline: List[Dict[str, str]] = []
        if use_tools:
            for tool_name in self.spec.tool_names:
                tool_func = TOOL_REGISTRY.get(tool_name)
                if not tool_func:
                    continue
                tool_details[tool_name] = tool_func(graph_data)
                tool_timeline.append({"工具名称": tool_name, "调用时机": "调用LLM前", "作用": TOOL_PURPOSE.get(tool_name, "")})
        else:
            tool_timeline.append({"工具名称": "无", "调用时机": "对照实验", "作用": "禁用工具，仅基于用户输入"})

        context_text = json.dumps(tool_details, ensure_ascii=False, indent=2) if tool_details else "（未使用工具）"
        final_user_prompt = (
            "【最新实时信息】\n"
            + user_input
            + "\n\n【历史信息（图谱工具抽取）】\n"
            + context_text
        )
        steps = ["读取图谱", "工具抽取", "构建Prompt", "调用LLM", "解析输出", "生成文档"]
        try:
            raw_text = invoke_qwen_with_retry(
                self.build_system_prompt(),
                final_user_prompt,
                config_path=config_path,
                required_tags=["思考", "正文"],
                max_retry=1,
            )
            thinking, body = parse_thinking_and_body(raw_text)
            result: Dict[str, Any] = {"success": True, "thinking": thinking, "text": body, "use_tools": use_tools}
            if self.spec.output_mode == "pdf":
                file_stem = self.spec.output_file_stem or self.spec.pdf_title
                pdf_path, md_path = write_report_outputs(
                    self.spec.pdf_title or self.spec.agent_name,
                    body,
                    self.spec.agent_code,
                    file_stem,
                )
                result["pdf_path"] = str(pdf_path)
                result["md_path"] = str(md_path)
                output_summary = f"已生成PDF:{pdf_path.name}, MD:{md_path.name}"
            else:
                output_summary = body[:120]
            self.logger.log(user_input[:500], steps, tool_timeline, tool_details, thinking, output_summary, "success")
            return result
        except Exception as exc:
            self.logger.log(user_input[:500], steps, tool_timeline, tool_details, "", "执行失败", "failed", str(exc))
            return {"success": False, "error": str(exc), "use_tools": use_tools}


def build_agent_node(runner: TaskAgentRunner, input_key: str, output_key: str) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def node(state: Dict[str, Any]) -> Dict[str, Any]:
        user_input = safe_text(state.get(input_key, ""))
        graph_path = Path(safe_text(state.get("graph_path", str(DEFAULT_GRAPH_PATH))))
        config_path = Path(safe_text(state.get("config_path", str(DEFAULT_CONFIG_PATH))))
        use_tools = state.get("use_tools", True)
        if isinstance(use_tools, str):
            use_tools = use_tools.lower() not in ("0", "false", "no")
        result = runner.run(user_input=user_input, graph_path=graph_path, config_path=config_path, use_tools=bool(use_tools))
        return {**state, output_key: result}

    return node
