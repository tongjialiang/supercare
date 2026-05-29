#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行 A0 流水线：生物标志物 Excel + 本地序贯分期 + 贝叶斯后验。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from staging.pipeline import run_full_staging_pipeline  # noqa: E402


def main() -> int:
    result = run_full_staging_pipeline()
    summary = {
        "success": result.get("success"),
        "focus_case_id": result.get("focus_case_id"),
        "excel_path": result.get("excel_path"),
        "staging_json_path": result.get("staging_json_path"),
        "bayesian_json_path": result.get("bayesian_json_path"),
        "cohort_case_count": result.get("cohort_case_count"),
        "focus_stage": (result.get("staging") or {})
        .get("focus_case_staging", {})
        .get("disease_stage_label"),
        "posterior_bpsd": (result.get("bayesian") or {}).get("posteriors", {}).get("bpsd_escalation_30d"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
