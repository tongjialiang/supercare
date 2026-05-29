# -*- coding: utf-8 -*-
"""分期结果缓存读取（本地 JSON）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from staging.bayesian_risk import DEFAULT_BAYESIAN_JSON
from staging.pipeline import run_full_staging_pipeline
from staging.sequential_staging_model import DEFAULT_STAGING_JSON

_MERGED_CACHE: Optional[Dict[str, Any]] = None


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_staging_bundle(
    force_refresh: bool = False,
    focus_case_id: Optional[str] = None,
    graph_path: Optional[Path] = None,
) -> Dict[str, Any]:
    global _MERGED_CACHE
    if not force_refresh and _MERGED_CACHE:
        return _MERGED_CACHE
    if not force_refresh and DEFAULT_STAGING_JSON.is_file() and DEFAULT_BAYESIAN_JSON.is_file():
        _MERGED_CACHE = {
            "staging": _read_json(DEFAULT_STAGING_JSON),
            "bayesian": _read_json(DEFAULT_BAYESIAN_JSON),
            "from_cache": True,
        }
        return _MERGED_CACHE
    pipeline_result = run_full_staging_pipeline(focus_case_id=focus_case_id, graph_path=graph_path)
    _MERGED_CACHE = {
        "staging": pipeline_result.get("staging", {}),
        "bayesian": pipeline_result.get("bayesian", {}),
        "excel_path": pipeline_result.get("excel_path"),
        "from_cache": False,
    }
    return _MERGED_CACHE
