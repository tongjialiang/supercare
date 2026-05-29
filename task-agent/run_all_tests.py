#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键执行全部测试并输出完整日志。"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from common_utils import LOG_DIR, TEST_DIR, create_pdf_report

ROOT = Path("/srv/supercare/task-agent")


def collect_test_files() -> List[Path]:
    return sorted(ROOT.glob("test_tool_*.py")) + sorted(ROOT.glob("test_agent_*.py"))


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    tests = collect_test_files()
    log_path = LOG_DIR / f"full_test_run_{started.strftime('%Y%m%d_%H%M%S')}.log"
    success_count = 0
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"开始时间: {started}\n")
        log_file.write(f"测试数量: {len(tests)}\n")
        for index, test_file in enumerate(tests, start=1):
            process = subprocess.run([sys.executable, str(test_file)], cwd=str(ROOT), capture_output=True, text=True)
            ok = process.returncode == 0
            success_count += int(ok)
            log_file.write(f"[{index}/{len(tests)}] {test_file.name} => {'success' if ok else 'failed'}\n")
            log_file.write("STDOUT:\n")
            log_file.write((process.stdout or "") + "\n")
            log_file.write("STDERR:\n")
            log_file.write((process.stderr or "") + "\n")
            log_file.write("=" * 80 + "\n")
    failed_count = len(tests) - success_count
    summary_pdf = TEST_DIR / f"full_test_summary_{started.strftime('%Y%m%d_%H%M%S')}.pdf"
    create_pdf_report(
        "TaskAgent 全量测试汇总",
        [
            f"开始时间：{started}",
            f"测试数量：{len(tests)}",
            f"成功数量：{success_count}",
            f"失败数量：{failed_count}",
            f"完整日志：{log_path}",
        ],
        summary_pdf,
    )
    print(f"完整日志路径: {log_path}")
    print(f"汇总报告路径: {summary_pdf}")
    if failed_count == 0:
        # 基于 A1-A14 产出 PDF 生成照护科学实践图谱（JSON + JPG）
        graph_script = ROOT / "generate_practice_knowledge_graph.py"
        if graph_script.is_file():
            graph_process = subprocess.run(
                [sys.executable, str(graph_script)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            if graph_process.returncode != 0:
                print("照护科学实践图谱生成失败（不影响测试通过状态）：")
                print((graph_process.stderr or graph_process.stdout or "").strip())
            else:
                print((graph_process.stdout or "").strip())
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
