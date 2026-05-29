# -*- coding: utf-8 -*-
"""A0 分期流水线：DataSource -> Excel -> 本地序贯分期 -> 贝叶斯。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from staging.bayesian_risk import compute_bayesian_posterior, save_bayesian_result
from staging.biomarker_extraction import (
    DEFAULT_EXCEL_OUTPUT,
    extract_cohort_biomarkers,
    write_biomarker_excel,
)
from staging.sustain_mcmc_model import (
    run_sustain_mcmc_staging,
    save_mcmc_staging_result,
    save_progression_curves_json,
)

DEFAULT_FOCUS_CASE_ID = "ms_chen"


def infer_focus_case_id_from_graph(graph_path: Optional[Path] = None) -> str:
    if not graph_path:
        return DEFAULT_FOCUS_CASE_ID
    match = re.search(r"([a-z]+)_CareCase", graph_path.name, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return DEFAULT_FOCUS_CASE_ID


def run_full_staging_pipeline(
    data_root: Path = Path("/srv/supercare/DataSource"),
    focus_case_id: Optional[str] = None,
    graph_path: Optional[Path] = None,
    new_observations: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    focus_id = focus_case_id or infer_focus_case_id_from_graph(graph_path)
    cohort = extract_cohort_biomarkers(data_root)
    excel_path = write_biomarker_excel(cohort, DEFAULT_EXCEL_OUTPUT)
    staging = run_sustain_mcmc_staging(cohort, focus_case_id=focus_id)
    staging_json = save_mcmc_staging_result(staging)
    save_progression_curves_json(
        {
            "focus_case_id": focus_id,
            "progression_curves": staging.get("progression_curves", {}),
            "mcmc_diagnostics": staging.get("mcmc_diagnostics", {}),
        }
    )
    bayesian = compute_bayesian_posterior(staging, focus_case_id=focus_id, new_observations=new_observations)
    bayesian_json = save_bayesian_result(bayesian)

    return {
        "success": True,
        "focus_case_id": focus_id,
        "excel_path": str(excel_path),
        "staging_json_path": str(staging_json),
        "bayesian_json_path": str(bayesian_json),
        "cohort_case_count": cohort.get("case_count", 0),
        "staging": staging,
        "bayesian": bayesian,
        "cohort_summary": {
            "extracted_at": cohort.get("extracted_at"),
            "cases": [case.get("case_id") for case in cohort.get("cases", [])],
        },
    }


if __name__ == "__main__":
    import json
    import sys

    task_agent_root = Path(__file__).resolve().parent.parent
    if str(task_agent_root) not in sys.path:
        sys.path.insert(0, str(task_agent_root))

    result = run_full_staging_pipeline()
    print(
        json.dumps(
            {
                "success": result.get("success"),
                "focus_case_id": result.get("focus_case_id"),
                "excel_path": result.get("excel_path"),
                "staging_json_path": result.get("staging_json_path"),
                "bayesian_json_path": result.get("bayesian_json_path"),
                "focus_stage": (result.get("staging") or {})
                .get("focus_case_staging", {})
                .get("disease_stage_label"),
                "posterior_bpsd": (result.get("bayesian") or {})
                .get("posteriors", {})
                .get("bpsd_escalation_30d"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    sys.exit(0 if result.get("success") else 1)
