#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按测试用例单次运行 A1–A14（启用工具），产出 PDF + Markdown。"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common_utils import DEFAULT_GRAPH_PATH  # noqa: E402
from staging.pipeline import run_full_staging_pipeline  # noqa: E402

# (模块名, 测试文件)
AGENT_RUNS: List[Tuple[str, str]] = [
    ("agent_a1_caa_hub", "test_agent_a1_caa_hub.py"),
    ("agent_a2_cca_hub", "test_agent_a2_cca_hub.py"),
    ("agent_a3_cda_hub", "test_agent_a3_cda_hub.py"),
    ("agent_a4_discharge_parser", "test_agent_a4_discharge_parser.py"),
    ("agent_a5_baseline_compare", "test_agent_a5_baseline_compare.py"),
    ("agent_a6_task_pack_agent", "test_agent_a6_task_pack_agent.py"),
    ("agent_a7_event_structuring_agent", "test_agent_a7_event_structuring_agent.py"),
    ("agent_a8_escalation_decision_agent", "test_agent_a8_escalation_decision_agent.py"),
    ("agent_a9_nursing_assessment_agent", "test_agent_a9_nursing_assessment_agent.py"),
    ("agent_a10_trend_comparison_agent", "test_agent_a10_trend_comparison_agent.py"),
    ("agent_a11_weekly_summary_agent", "test_agent_a11_weekly_summary_agent.py"),
    ("agent_a12_consult_agent", "test_agent_a12_consult_agent.py"),
    ("agent_a13_outcome_report_agent", "test_agent_a13_outcome_report_agent.py"),
    ("agent_a14_audit_eval_agent", "test_agent_a14_audit_eval_agent.py"),
]


def load_prompt_from_test(test_filename: str) -> str:
    """从 test_agent_*.py 中解析 prompt 字符串（含 if __main__ 块内）。"""
    source = (ROOT / test_filename).read_text(encoding="utf-8")
    module = ast.parse(source)
    for node in ast.walk(module):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "prompt":
                value = ast.literal_eval(node.value)
                if isinstance(value, str):
                    return value
    raise ValueError(f"未在 {test_filename} 中找到 prompt 赋值")


def import_run_agent(module_name: str) -> Callable[..., Dict]:
    module = __import__(module_name, fromlist=["run_agent"])
    return module.run_agent


def collect_output_paths(result: Dict) -> List[str]:
    paths: List[str] = []
    for key in ("pdf_path", "md_path", "jsonl_path"):
        value = result.get(key)
        if value:
            paths.append(str(value))
    for key in ("pdf_paths", "md_paths"):
        values = result.get(key)
        if isinstance(values, list):
            paths.extend(str(item) for item in values)
    return paths


def main() -> int:
    graph_path = Path(DEFAULT_GRAPH_PATH)
    failed: List[str] = []
    print(f"图谱路径: {graph_path}")
    print(f"产出目录: {ROOT / 'output'}\n")

    print("[A0] 本地序贯分期 + 贝叶斯风险流水线 ...", flush=True)
    try:
        staging_summary = run_full_staging_pipeline(graph_path=graph_path)
        print(
            f"  病例数={staging_summary.get('cohort_case_count')}, "
            f"焦点={staging_summary.get('focus_case_id')}, "
            f"Excel={staging_summary.get('excel_path')}\n",
            flush=True,
        )
    except Exception as staging_error:
        print(f"  A0 流水线失败（继续运行 A1-A14）: {staging_error}\n", flush=True)

    for index, (module_name, test_file) in enumerate(AGENT_RUNS, start=1):
        agent_label = module_name.replace("agent_", "").upper()
        print(f"[{index}/14] {agent_label} ...", flush=True)
        try:
            prompt = load_prompt_from_test(test_file)
            run_agent = import_run_agent(module_name)
            result = run_agent(prompt, graph_path=graph_path, use_tools=True)
            if not result.get("success"):
                failed.append(agent_label)
                print(f"  FAILED: {result.get('error', '未知错误')}")
                continue
            for path in collect_output_paths(result):
                print(f"  -> {path}")
        except Exception as exc:
            failed.append(agent_label)
            print(f"  ERROR: {exc}")

    print()
    if failed:
        print(f"失败: {', '.join(failed)}")
        return 1
    print("A1–A14 全部完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
