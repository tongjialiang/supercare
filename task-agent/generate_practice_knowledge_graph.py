#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 A1-A14 智能体产出 PDF 凝练「照护科学实践图谱」，输出 JSON + JPG。

运行：python /srv/supercare/task-agent/generate_practice_knowledge_graph.py
依赖：pypdf、networkx、Pillow；中文字体首次运行会尝试下载到 fonts/ 目录。
"""

from __future__ import annotations

import json
import math
import re
import textwrap
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from PIL import Image, ImageDraw, ImageFont

from common_utils import (
    DEFAULT_CONFIG_PATH,
    OUTPUT_DIR,
    ensure_dirs,
    load_qwen_config,
    save_json,
    safe_text,
)

PROJECT_ROOT = Path(__file__).resolve().parent
FONT_DIR = PROJECT_ROOT / "fonts"
FONT_FILENAME = "SourceHanSansCN-Regular.otf"
FONT_URL = (
    "https://mirrors.tuna.tsinghua.edu.cn/adobe-fonts/source-han-sans/"
    "SubsetOTF/CN/SourceHanSansCN-Regular.otf"
)

# 仅纳入 A1-A14 智能体 PDF（排除 jsonl 等非 PDF）
AGENT_PDF_PATTERN = re.compile(r"^a(1[0-4]|[1-9])_.+\.pdf$", re.IGNORECASE)

KG_JSON_NAME = "照护科学实践图谱.json"
KG_JPG_NAME = "照护科学实践图谱.jpg"

# 图谱必须以三职业智能体为认知中枢（与模型约定 id，便于分层布局）
CORE_NODE_IDS = ("CORE_A1_SUPER_CAREGIVER", "CORE_A2_SUPER_NURSE", "CORE_A3_SUPER_GP")

ALLOWED_NODE_CATEGORIES = (
    "核心智能体",
    "角色",
    "文档产出",
    "照护流程",
    "风险要素",
    "干预措施",
    "评估维度",
    "协同机制",
    "制度与质控",
    "行业知识命题",
)


def normalize_category(value: str) -> str:
    """将模型输出的类别映射到预设专业类别。"""
    text = safe_text(value)
    if text in ALLOWED_NODE_CATEGORIES:
        return text
    mapping = {
        "超级角色": "核心智能体",
        "认知中枢": "核心智能体",
        "长者": "角色",
        "老人": "角色",
        "健康问题": "风险要素",
        "风险因素": "风险要素",
        "行为特征": "照护流程",
        "照护目标": "评估维度",
        "防护措施": "干预措施",
        "协作策略": "协同机制",
        "干预切入点": "干预措施",
        "方法论": "行业知识命题",
        "可迁移知识": "行业知识命题",
    }
    return mapping.get(text, "文档产出")


def normalize_graph_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """统一节点类别与边的字段名，过滤无效边。"""
    title = safe_text(payload.get("title")) or "照护科学实践图谱"
    summary = safe_text(payload.get("summary")) or ""
    raw_nodes = payload.get("nodes") or []
    raw_edges = payload.get("edges") or []
    nodes: List[Dict[str, str]] = []
    node_ids: set[str] = set()
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        node_id = safe_text(item.get("id"))
        if not node_id:
            continue
        label = safe_text(item.get("label")) or node_id
        category = normalize_category(safe_text(item.get("category")))
        nodes.append({"id": node_id, "label": label[:48], "category": category})
        node_ids.add(node_id)

    edges: List[Dict[str, str]] = []
    for item in raw_edges:
        if not isinstance(item, dict):
            continue
        source = safe_text(item.get("source") or item.get("from"))
        target = safe_text(item.get("target") or item.get("to"))
        relation = safe_text(item.get("relation") or item.get("label") or item.get("type")) or "关联"
        if source in node_ids and target in node_ids:
            edges.append({"source": source, "target": target, "relation": relation[:28]})

    return {"title": title, "summary": summary, "nodes": nodes, "edges": edges}


def ensure_three_core_hubs(graph: Dict[str, Any]) -> Dict[str, Any]:
    """保证三超级职业节点存在并置于 nodes 前列，便于科研阅读与布局。"""
    nodes_in = [n for n in graph.get("nodes") or [] if isinstance(n, dict) and safe_text(n.get("id"))]
    edges_in = [e for e in graph.get("edges") or [] if isinstance(e, dict)]
    by_id: Dict[str, Dict[str, str]] = {}
    for item in nodes_in:
        nid = safe_text(item.get("id"))
        by_id[nid] = {
            "id": nid,
            "label": safe_text(item.get("label")) or nid,
            "category": normalize_category(safe_text(item.get("category"))),
        }
    core_defs = [
        {
            "id": "CORE_A1_SUPER_CAREGIVER",
            "label": "超级照护员（A1协作中枢）",
            "category": "核心智能体",
        },
        {
            "id": "CORE_A2_SUPER_NURSE",
            "label": "超级护士（A2协作中枢）",
            "category": "核心智能体",
        },
        {
            "id": "CORE_A3_SUPER_GP",
            "label": "超级全科医师-GP（A3协作中枢）",
            "category": "核心智能体",
        },
    ]
    for core in core_defs:
        if core["id"] not in by_id:
            by_id[core["id"]] = dict(core)
    ordered_nodes: List[Dict[str, str]] = []
    for cid in CORE_NODE_IDS:
        if cid in by_id:
            ordered_nodes.append(by_id[cid])
    for nid, payload in by_id.items():
        if nid in CORE_NODE_IDS:
            continue
        ordered_nodes.append(payload)
    return {
        "title": graph.get("title"),
        "summary": graph.get("summary"),
        "nodes": ordered_nodes,
        "edges": edges_in,
    }


def ensure_chinese_font() -> Optional[Path]:
    """确保存在可渲染中文的字体文件。"""
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    font_path = FONT_DIR / FONT_FILENAME
    if font_path.is_file() and font_path.stat().st_size > 1_000_000:
        return font_path
    try:
        print(f"正在下载中文字体（约 8MB）至 {font_path} …")
        urllib.request.urlretrieve(FONT_URL, str(font_path))  # noqa: S310 可信镜像
        return font_path
    except OSError as exc:
        print(f"字体下载失败（{exc}），将尝试系统字体；中文可能显示为方框。")
        return None


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """加载支持中文的 TrueType/OpenType 字体。"""
    path = ensure_chinese_font()
    if path and path.is_file():
        return ImageFont.truetype(str(path), size=size)
    # 常见系统路径回退
    for candidate in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        p = Path(candidate)
        if p.is_file():
            return ImageFont.truetype(str(p), size=size)
    return ImageFont.load_default()


def list_agent_pdfs(output_dir: Path) -> List[Path]:
    """列出 output 下属于 A1-A14 的 PDF，按智能体编号排序。"""
    files: List[Tuple[int, Path]] = []
    for pdf_path in sorted(output_dir.glob("a*.pdf")):
        if not AGENT_PDF_PATTERN.match(pdf_path.name):
            continue
        match = re.match(r"^a(\d+)_", pdf_path.name, re.IGNORECASE)
        if not match:
            continue
        code = int(match.group(1))
        if 1 <= code <= 14:
            files.append((code, pdf_path))
    files.sort(key=lambda item: (item[0], item[1].name))
    return [path for _, path in files]


def extract_pdf_text(pdf_path: Path, max_chars: int = 900) -> str:
    """从 PDF 抽取纯文本（截断以防超长）。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        reader = PdfReader(str(pdf_path))
        chunks: List[str] = []
        for page in reader.pages:
            chunks.append(safe_text(page.extract_text()))
        text = "\n".join(chunks).strip()
        if len(text) > max_chars:
            return text[:max_chars] + "\n…（已截断）"
        return text
    except OSError:
        return ""


def build_corpus(pdf_paths: List[Path]) -> str:
    """拼装多份 PDF 摘要供大模型凝练图谱。"""
    sections: List[str] = []
    for pdf_path in pdf_paths:
        body = extract_pdf_text(pdf_path)
        sections.append(f"【文件】{pdf_path.name}\n{body or '（未能抽取文本）'}")
    return "\n\n".join(sections)


def extract_json_object(raw: str) -> Optional[Dict[str, Any]]:
    """从大模型输出中解析 JSON 对象。"""
    text = safe_text(raw)
    text = re.sub(r"<思考>[\s\S]*?</思考>", "", text, flags=re.IGNORECASE).strip()
    body_match = re.search(r"<正文>([\s\S]*?)</正文>", text, flags=re.IGNORECASE)
    if body_match:
        text = body_match.group(1).strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start : end + 1]
    # 常见模型误用中文引号，尝试替换
    candidate = candidate.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def invoke_qwen_for_graph(system_prompt: str, user_prompt: str, config_path: Path) -> str:
    """图谱 JSON 体量较大，单独提高 max_tokens，降低截断概率。"""
    from openai import OpenAI

    config = load_qwen_config(config_path)
    if not safe_text(config["api_key"]):
        return ""
    client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
    response = client.chat.completions.create(
        model=config["model"],
        temperature=min(float(config["temperature"]), 0.3),
        max_tokens=max(int(config["max_tokens"]), 8192),
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
    )
    return safe_text(response.choices[0].message.content)


def llm_build_knowledge_graph(corpus: str, config_path: Path) -> Dict[str, Any]:
    """调用 Qwen 将实践产出凝练为「照护科学实践图谱」（以三超级角色为核心）。"""
    system_prompt = """你是照护科学（Care Science）与老年照护信息化交叉领域专家。
【图谱目的】本次产出为「照护科学实践图谱」：服务于照护科学行业长期知识积累与可复用命题沉淀，供科研人员理解与二次研究；
不得将图谱叙事中心写成「为某位具体老人提供照料」——个案文本仅作为证据来源，须抽象为可迁移的概念、机制、流程与决策逻辑。
【认知中枢（强制）】图谱必须以以下三个节点为全局核心（id 与 label 必须完全一致，且必须出现在 nodes 最前三条）：
1) id=CORE_A1_SUPER_CAREGIVER，label=超级照护员（A1协作中枢），category=核心智能体
2) id=CORE_A2_SUPER_NURSE，label=超级护士（A2协作中枢），category=核心智能体
3) id=CORE_A3_SUPER_GP，label=超级全科医师-GP（A3协作中枢），category=核心智能体
【层次结构】其余节点须体现层次：①与三核心直接相连的方法论/证据域；②从 A4-A14 报告抽象出的可复用「行业知识命题」、工具化产出、风险—干预—质控链条；③尽量包含教材中较少系统阐述、但实践报告体现的「隐性照护知识」（如非药物干预设计、升级阈值、多学科协同接口等）。
【输出格式】仅输出一段合法 UTF-8 JSON，禁止 Markdown、禁止代码围栏、禁止 <思考>、禁止 JSON 外任何文字。
JSON 顶层结构：
{
  "title": "中文标题（突出照护科学实践图谱与三核心）",
  "summary": "180-280字：说明本图谱对科研与行业的价值，强调可复用知识与三角色分工，勿以个案姓名为中心叙事",
  "nodes": [ {"id":"…","label":"…","category":"…"} ],
  "edges": [ {"source":"…","target":"…","relation":"…"} 或 {"from","to","label"} ]
}
【类别】category 只能取自：核心智能体|角色|文档产出|照护流程|风险要素|干预措施|评估维度|协同机制|制度与质控|行业知识命题
【规模】nodes 必须 48-62 条；edges 必须 62-88 条；label 每条不超过 22 个汉字；relation 用专业短语（可略长以表意完整）。
【边逻辑】大量边应连接三核心之一与知识域/命题/流程节点，体现辐射与分工；并保留 A4→A5→A6→… 等流程向边（可用抽象节点表示阶段）。"""
    user_prompt = f"""以下为 TaskAgent A1-A14 报告 PDF 抽取文本（含个案表述，仅供抽象，勿以姓名为图谱中心）：

{corpus}

请生成符合上述全部约束的 JSON。"""
    raw = invoke_qwen_for_graph(system_prompt, user_prompt, config_path=config_path)
    parsed = extract_json_object(raw)
    if not isinstance(parsed, dict):
        return {}
    normalized = normalize_graph_payload(parsed)
    nodes = normalized.get("nodes") or []
    edges = normalized.get("edges") or []
    # 强制存在三核心节点（若模型漏掉则补全并尽量连边）
    normalized = ensure_three_core_hubs(normalized)
    nodes = normalized.get("nodes") or []
    edges = normalized.get("edges") or []
    if len(nodes) < 30 or len(edges) < 45:
        return {}
    return normalized


def fallback_graph(pdf_paths: List[Path]) -> Dict[str, Any]:
    """大模型不可用时：仍以三超级职业为核心，生成行业向保底图谱（节点较多、分层清晰）。"""
    nodes: List[Dict[str, str]] = [
        {
            "id": "CORE_A1_SUPER_CAREGIVER",
            "label": "超级照护员（A1协作中枢）",
            "category": "核心智能体",
        },
        {
            "id": "CORE_A2_SUPER_NURSE",
            "label": "超级护士（A2协作中枢）",
            "category": "核心智能体",
        },
        {
            "id": "CORE_A3_SUPER_GP",
            "label": "超级全科医师-GP（A3协作中枢）",
            "category": "核心智能体",
        },
    ]
    edges: List[Dict[str, str]] = []

    # 文档与流程层（与 A4-A14 对应，抽象为行业可复用模块）
    doc_nodes = [
        ("MOD_A4", "出院摘要结构化（循证入院接口）", "文档产出"),
        ("MOD_A5", "ECR纵向状态对比方法", "文档产出"),
        ("MOD_A6", "返院适应期任务拆解与频次化", "文档产出"),
        ("MOD_A7", "BPSD现场记录结构化范式", "文档产出"),
        ("MOD_A8", "风险升级与处置分级规则", "照护流程"),
        ("MOD_A9", "护理评估—周任务双轨输出", "文档产出"),
        ("MOD_A10", "三时点功能趋势表达", "评估维度"),
        ("MOD_A11", "周报—会诊证据打包", "文档产出"),
        ("MOD_A12", "远程精神科会诊记录规范", "协同机制"),
        ("MOD_A13", "中期/D30成效复盘框架", "文档产出"),
        ("MOD_A14", "多智能体输出质控与审计", "制度与质控"),
    ]
    for nid, lab, cat in doc_nodes:
        nodes.append({"id": nid, "label": lab, "category": cat})

    # 行业知识命题（书上难系统覆盖的实践型知识）
    propositions = [
        "兴趣嵌入型非药物干预与依从性",
        "跌倒—服药—镇静剂三角风险管理",
        "家属焦虑的协同沟通与反馈节律",
        "升级阈值与「观察—护士—GP」分流",
        "任务频次化与可执行颗粒度设计",
        "三时点数据对功能衰退早期信号",
        "会诊问题清单驱动的循证决策",
        "皮肤完整性与隐匿性外伤线索",
        "心率偏低与起搏器情境下的活动处方",
        "认知波动期与社交退缩的区分照护",
        "舞蹈类活动中的认知负荷拆分",
        "照护记录缺口对质量评估的偏倚",
        "重复用药记录与依从性误判",
        "夜醒与离床行为的多源解释框架",
        "返院链路的文档—对比—任务闭环",
        "结构化出院包与机构承接清单对齐",
        "ECR对比中的「恶化/稳定/改善」判定口径",
        "BPSD复合事件与单一症状记录区分",
        "精神科药物与跌倒风险的权衡提示",
        "周报中的「决策待办」与责任边界",
        "D30再稳定与中期目标的衔接指标",
        "审计视角下的溯源字段与可复核性",
        "图谱工具与实时输入的冲突消解原则",
        "多角色文本中的术语对齐与消歧",
        "机构内非药物干预的证据等级自评",
        "跨周趋势与偶发波动的统计直觉",
        "照护员直觉与量表结论的三角校验",
    ]
    for index, text in enumerate(propositions, start=1):
        nodes.append({"id": f"KP_{index:02d}", "label": text, "category": "行业知识命题"})

    # 三核心 → 行业命题（均衡辐射，增强层次）
    for index in range(1, len(propositions) + 1):
        kid = f"KP_{index:02d}"
        bucket = index % 3
        if bucket == 0:
            edges.append({"source": "CORE_A1_SUPER_CAREGIVER", "target": kid, "relation": "一线情境知识沉淀"})
        elif bucket == 1:
            edges.append({"source": "CORE_A2_SUPER_NURSE", "target": kid, "relation": "护理与评估知识沉淀"})
        else:
            edges.append({"source": "CORE_A3_SUPER_GP", "target": kid, "relation": "医疗与协同知识沉淀"})

    # 三核心 → 各模块（辐射）
    for nid, _, _ in doc_nodes:
        if nid in ("MOD_A4", "MOD_A6", "MOD_A7", "MOD_A11"):
            edges.append({"source": "CORE_A1_SUPER_CAREGIVER", "target": nid, "relation": "一线执行与证据生成"})
        elif nid in ("MOD_A5", "MOD_A9", "MOD_A10", "MOD_A8"):
            edges.append({"source": "CORE_A2_SUPER_NURSE", "target": nid, "relation": "评估与流程质控"})
        else:
            edges.append({"source": "CORE_A3_SUPER_GP", "target": nid, "relation": "医疗决策与协同接口"})

    # 模块 → 行业命题（抽样连接，形成层次）
    link_pairs = [
        ("MOD_A6", "KP_05", "任务设计支撑"),
        ("MOD_A7", "KP_01", "事件范式支撑"),
        ("MOD_A8", "KP_04", "规则沉淀"),
        ("MOD_A9", "KP_02", "评估联动"),
        ("MOD_A10", "KP_06", "趋势解释"),
        ("MOD_A12", "KP_07", "会诊驱动"),
        ("MOD_A13", "KP_15", "成效框架"),
        ("MOD_A14", "KP_12", "质控对象"),
        ("MOD_A4", "KP_15", "入院接口"),
        ("MOD_A5", "KP_06", "纵向证据"),
        ("MOD_A11", "KP_03", "沟通节律"),
        ("MOD_A6", "KP_01", "非药物路径"),
        ("MOD_A7", "KP_04", "升级依据"),
        ("MOD_A9", "KP_13", "记录质量"),
        ("MOD_A1", "KP_08", "体征情境"),
    ]
    # 修正 MOD_A1 不存在，改为 CORE_A1 → KP_08
    link_pairs[-1] = ("CORE_A1_SUPER_CAREGIVER", "KP_08", "体征情境整合")
    for src, tgt, rel in link_pairs:
        edges.append({"source": src, "target": tgt, "relation": rel})

    # 流程链
    chain = ["MOD_A4", "MOD_A5", "MOD_A6", "MOD_A7", "MOD_A8", "MOD_A11", "MOD_A12", "MOD_A13"]
    for left, right in zip(chain, chain[1:]):
        edges.append({"source": left, "target": right, "relation": "阶段衔接"})

    # 命题间弱关联（体现科研网络）
    extra = [
        ("KP_01", "KP_03", "与家属协同"),
        ("KP_02", "KP_04", "风险叠加"),
        ("KP_05", "KP_12", "可执行性"),
        ("KP_06", "KP_10", "功能解释"),
        ("KP_07", "KP_14", "证据整合"),
        ("KP_09", "KP_08", "躯体限制"),
        ("KP_11", "KP_01", "干预细化"),
        ("KP_13", "KP_12", "数据质量"),
    ]
    for a, b, r in extra:
        edges.append({"source": a, "target": b, "relation": r})

    return {
        "title": "照护科学实践图谱：以超级照护员—超级护士—超级GP为核心（保底）",
        "summary": (
            "本照护科学实践图谱在离线模式下仍以 A1/A2/A3 三职业智能体为认知中枢，辐射文档化产出、流程规则与可复用行业命题，"
            "强调照护科学中「隐性实践知识」的结构化沉淀，而非个案照料叙事；完整语义凝练需大模型成功返回 JSON。"
        ),
        "nodes": nodes,
        "edges": edges,
    }


def category_color(category: str) -> Tuple[int, int, int]:
    """按节点类别返回专业配色（柔和区分）。"""
    palette = {
        "核心智能体": (123, 31, 162),
        "角色": (41, 98, 155),
        "文档产出": (34, 139, 34),
        "照护流程": (178, 34, 34),
        "风险要素": (204, 85, 0),
        "干预措施": (0, 120, 140),
        "评估维度": (0, 128, 128),
        "协同机制": (70, 130, 180),
        "制度与质控": (105, 105, 105),
        "行业知识命题": (196, 120, 40),
    }
    return palette.get(category, (60, 60, 60))


def _resolve_core_node_ids(graph_nx: nx.DiGraph) -> List[str]:
    """解析三超级职业节点 id（优先约定 id，其次按标签推断）。"""
    ordered: List[str] = []
    for cid in CORE_NODE_IDS:
        if graph_nx.has_node(cid):
            ordered.append(cid)
    if len(ordered) >= 3:
        return ordered
    for node_id, data in graph_nx.nodes(data=True):
        lab = safe_text(data.get("label", ""))
        if ("超级照护员" in lab) or ("A1" in lab and "照护" in lab):
            if node_id not in ordered:
                ordered.append(node_id)
        elif ("超级护士" in lab) or ("A2" in lab and "护士" in lab):
            if node_id not in ordered:
                ordered.append(node_id)
        elif ("超级全科" in lab) or ("超级GP" in lab) or ("A3" in lab and "GP" in lab):
            if node_id not in ordered:
                ordered.append(node_id)
    if len(ordered) >= 3:
        return ordered[:3]
    ranked = sorted(graph_nx.nodes(), key=lambda n: graph_nx.degree(n), reverse=True)
    for nid in ranked:
        if nid not in ordered:
            ordered.append(nid)
        if len(ordered) >= 3:
            break
    return ordered[:3]


def _shell_nlist(graph_nx: nx.DiGraph, cores: List[str]) -> List[List[str]]:
    """按与三核心的图距离分层，形成同心壳层（科研可读）。"""
    core_set = set(cores)
    rest = [n for n in graph_nx.nodes if n not in core_set]
    if not rest:
        return [cores] if cores else [list(graph_nx.nodes())]
    und = graph_nx.to_undirected()
    shell1: List[str] = []
    shell2: List[str] = []
    shell_far: List[str] = []
    for node_id in rest:
        dist_min = 999
        for core_id in cores:
            if core_id not in und or node_id not in und:
                continue
            try:
                dist_min = min(dist_min, nx.shortest_path_length(und, core_id, node_id))
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
        if dist_min == 1:
            shell1.append(node_id)
        elif dist_min == 2:
            shell2.append(node_id)
        else:
            shell_far.append(node_id)
    shells: List[List[str]] = [cores, shell1, shell2, shell_far]
    return [layer for layer in shells if layer]


def _wrap_label_lines(label: str, chars_per_line: int) -> List[str]:
    text = safe_text(label)
    if not text:
        return [""]
    lines = textwrap.wrap(text, width=chars_per_line)
    return lines if lines else [text]


def _multiline_block_height(draw: ImageDraw.ImageDraw, lines: List[str], font: ImageFont.FreeTypeFont) -> int:
    total = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        total += bbox[3] - bbox[1] + 5
    return total


def render_graph_jpg(graph: Dict[str, Any], jpg_path: Path, width: int = 4600, height: int = 3400) -> None:
    """分层 shell 布局 + 节点内中文换行，便于科研人员完整阅读。"""
    nodes_raw = graph.get("nodes") or []
    edges_raw = graph.get("edges") or []
    title = safe_text(graph.get("title")) or "照护科学实践图谱（三核心）"
    summary = safe_text(graph.get("summary", ""))

    graph_nx = nx.DiGraph()
    for node in nodes_raw:
        if not isinstance(node, dict):
            continue
        node_id = safe_text(node.get("id"))
        if not node_id:
            continue
        graph_nx.add_node(
            node_id,
            label=safe_text(node.get("label")) or node_id,
            category=safe_text(node.get("category")) or "文档产出",
        )
    for edge in edges_raw:
        if not isinstance(edge, dict):
            continue
        source = safe_text(edge.get("source"))
        target = safe_text(edge.get("target"))
        if source and target and graph_nx.has_node(source) and graph_nx.has_node(target):
            graph_nx.add_edge(source, target, relation=safe_text(edge.get("relation")) or "关联")

    if graph_nx.number_of_nodes() == 0:
        graph_nx.add_node("empty", label="无节点数据", category="制度与质控")

    cores = _resolve_core_node_ids(graph_nx)
    shells = _shell_nlist(graph_nx, cores)
    try:
        pos = nx.shell_layout(graph_nx, nlist=shells, scale=4.2)
    except (ValueError, nx.NetworkXError):
        pos = nx.spring_layout(graph_nx, seed=42, k=2.8 / math.sqrt(max(graph_nx.number_of_nodes(), 1)), iterations=120)

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 0.25)
    span_y = max(max_y - min_y, 0.25)

    margin_x, margin_y = 140, 160
    header_h = 150
    footer_h = 120
    usable_w = width - 2 * margin_x
    usable_h = height - header_h - footer_h - margin_y

    def to_pixel(node_id: str) -> Tuple[float, float]:
        x, y = pos[node_id]
        px = margin_x + (x - min_x) / span_x * usable_w
        py = margin_y + (y - min_y) / span_y * usable_h
        py = height - footer_h - margin_y - (py - margin_y)
        return px, py

    image = Image.new("RGB", (width, height), (248, 249, 252))
    draw = ImageDraw.Draw(image)
    font_title = load_font(32)
    font_sub = load_font(20)
    font_node = load_font(17)
    font_edge = load_font(12)
    font_legend = load_font(16)

    draw.rectangle([0, 0, width, header_h], fill=(236, 240, 245))
    title_lines = textwrap.wrap(title, width=38)[:2]
    for row, tl in enumerate(title_lines):
        draw.text((margin_x, 22 + row * 40), tl, fill=(18, 28, 42), font=font_title)
    if summary:
        sub_lines = textwrap.wrap(summary, width=56)[:2]
        for row, sl in enumerate(sub_lines):
            draw.text((margin_x, 92 + row * 28), sl, fill=(70, 78, 90), font=font_sub)

    # 边（略细，关系文字完整换行）
    for source, target, data in graph_nx.edges(data=True):
        x1, y1 = to_pixel(source)
        x2, y2 = to_pixel(target)
        draw.line([(x1, y1), (x2, y2)], fill=(200, 206, 218), width=1)
        relation = safe_text(data.get("relation"))
        if relation:
            rel_lines = textwrap.wrap(relation, width=10)[:2]
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            ry = mid_y - 8
            for rl in rel_lines:
                rb = draw.textbbox((0, 0), rl, font=font_edge)
                rw = rb[2] - rb[0]
                draw.rectangle(
                    [mid_x - rw / 2 - 3, ry - 2, mid_x + rw / 2 + 3, ry + (rb[3] - rb[1]) + 2],
                    fill=(248, 249, 252),
                    outline=(220, 224, 232),
                )
                draw.text((mid_x - rw / 2, ry), rl, fill=(90, 96, 110), font=font_edge)
                ry += (rb[3] - rb[1]) + 3

    # 节点（圆角矩形 + 多行中文，核心节点略大字号）
    for node_id in graph_nx.nodes:
        px, py = to_pixel(node_id)
        category = graph_nx.nodes[node_id].get("category", "")
        color = category_color(category)
        label = graph_nx.nodes[node_id].get("label", node_id)
        is_core = node_id in CORE_NODE_IDS or category == "核心智能体"
        wrap_w = 14 if is_core else 11
        font_use = load_font(19) if is_core else font_node
        lines = _wrap_label_lines(label, wrap_w)
        block_h = _multiline_block_height(draw, lines, font_use)
        line_widths: List[int] = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_use)
            line_widths.append(bbox[2] - bbox[0])
        rect_w = max(line_widths, default=40) + 36
        rect_h = block_h + 28
        bbox_rect = [px - rect_w / 2, py - rect_h / 2, px + rect_w / 2, py + rect_h / 2]
        outline_w = 3 if is_core else 2
        draw.rounded_rectangle(bbox_rect, radius=12, fill=color, outline=(255, 255, 255), width=outline_w)
        cursor_y = py - block_h / 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_use)
            lw = bbox[2] - bbox[0]
            draw.text((px - lw / 2, cursor_y), line, fill=(255, 255, 255), font=font_use)
            cursor_y += bbox[3] - bbox[1] + 5

    # 图例（左下角）
    legend_x = margin_x
    legend_y = height - footer_h + 10
    draw.text((legend_x, legend_y), "节点类别（科研导读）", fill=(40, 44, 52), font=font_legend)
    legend_y += 34
    seen: set[str] = set()
    col = 0
    for node_id in graph_nx.nodes:
        cat = graph_nx.nodes[node_id].get("category", "")
        if cat in seen:
            continue
        seen.add(cat)
        color = category_color(cat)
        lx = legend_x + col * 420
        if lx > width - 400:
            col = 0
            legend_y += 30
            lx = legend_x
        draw.rounded_rectangle([lx, legend_y, lx + 20, legend_y + 20], radius=4, fill=color)
        draw.text((lx + 28, legend_y), cat, fill=(40, 44, 52), font=font_edge)
        col += 1

    jpg_path.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(str(jpg_path), format="JPEG", quality=93, optimize=True)


def main() -> int:
    ensure_dirs()
    FONT_DIR.mkdir(parents=True, exist_ok=True)

    pdf_paths = list_agent_pdfs(OUTPUT_DIR)
    if not pdf_paths:
        print(f"未在 {OUTPUT_DIR} 找到 A1-A14 的 PDF，请先运行智能体测试生成报告。")
        return 1

    corpus = build_corpus(pdf_paths)
    graph = llm_build_knowledge_graph(corpus, DEFAULT_CONFIG_PATH)
    if not graph:
        print("大模型未返回有效 JSON，使用保底图谱结构。")
        graph = fallback_graph(pdf_paths)

    graph["_meta"] = {
        "说明": "照护科学实践图谱：由 TaskAgent A1-A14 实践 PDF 凝练；以超级照护员、超级护士、超级 GP 为三认知核心，服务照护科学行业知识积累",
        "三核心节点": list(CORE_NODE_IDS),
        "来源PDF": [path.name for path in pdf_paths],
    }

    json_path = OUTPUT_DIR / KG_JSON_NAME
    jpg_path = OUTPUT_DIR / KG_JPG_NAME
    save_json(json_path, graph)
    render_graph_jpg(graph, jpg_path)

    print(f"照护科学实践图谱 JSON：{json_path}")
    print(f"照护科学实践图谱 JPG：{jpg_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
