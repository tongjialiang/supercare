#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A0 流水线单元测试（不调用 LLM）。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_疾病分期洞察, tool_贝叶斯风险后验
from staging.pipeline import run_full_staging_pipeline


def main() -> int:
    result = run_full_staging_pipeline(graph_path=DEFAULT_GRAPH_PATH)
    assert result.get("success"), "流水线应成功"
    assert result.get("cohort_case_count", 0) >= 1, "应至少 1 例病例"
    excel = Path(result["excel_path"])
    assert excel.is_file(), f"缺少 Excel: {excel}"

    graph = load_graph()
    staging_tool = tool_疾病分期洞察(graph)
    bayes_tool = tool_贝叶斯风险后验(graph)
    focus = staging_tool.get("焦点病例分期", {})
    assert focus.get("disease_stage") or focus.get("sustain_stage"), "应有疾病阶段"
    assert bayes_tool.get("后验概率"), "应有贝叶斯后验"
    assert "SuStaIn" not in staging_tool.get("模型说明", ""), "不应出现外部产品名"

    print("A0 测试通过")
    print("  阶段:", focus.get("disease_stage_label") or focus.get("sustain_stage_label"))
    print("  后验 BPSD:", bayes_tool["后验概率"].get("bpsd_escalation_30d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
