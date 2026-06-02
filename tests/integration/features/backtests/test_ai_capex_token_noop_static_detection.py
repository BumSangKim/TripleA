from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from api.features.backtests.ai_capex_token_tuning_execution_test import (
    run_ai_capex_token_tuning_execution_test,
)


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token_tuning")


def test_all_equal_output_candidate_set_fails_noop_tuning():
    report = _run_with_static_candidates()

    assert report["unique_parameter_hash_count"] == 3
    assert report["unique_output_signature_count"] == 1
    assert report["unique_metric_signature_count"] == 1
    assert report["status"] == "FAIL_NOOP_TUNING"
    assert report["no_op_tuning_detected"] is True


def test_duplicate_output_candidates_are_rejected_with_no_variation_reason():
    report = _run_with_static_candidates()

    rejected = report["rejected_candidates"]

    assert rejected
    assert all("NO_OUTPUT_VARIATION" in candidate["reject_reasons"] for candidate in rejected)
    assert report["selected_candidate_id"] == "baseline"


def test_static_parameter_candidate_does_not_win_by_input_order_noise():
    report = _run_with_static_candidates()
    scores = {result["candidate"]["candidate_id"]: result["objective_score"] for result in report["candidates"]}

    assert scores["static_a"] == scores["baseline"]
    assert scores["static_b"] == scores["baseline"]
    assert report["selected_candidate_id"] not in {"static_a", "static_b"}
    assert report["production_ready"] is False


def _run_with_static_candidates() -> dict:
    candidate_grid = {
        "metadata": {
            "fixture_id": "ai_capex_token_static_noop_grid_v1",
            "diagnostic_only": True,
            "production_enabled": False,
            "approved": False,
        },
        "candidates": [
            _candidate("baseline", "base"),
            _candidate("static_a", "unused-a"),
            _candidate("static_b", "unused-b"),
        ],
    }
    fixture = json.loads((FIXTURE_DIR / "synthetic_two_memory_cycles.json").read_text(encoding="utf-8"))
    return run_ai_capex_token_tuning_execution_test(
        candidate_grid=candidate_grid,
        snapshots=fixture["snapshots"],
    )


def _candidate(candidate_id: str, marker: str) -> dict:
    parameters = {
        "normalization_strength": 0.5,
        "scenario_smoothing_alpha": 0.5,
        "sector_component_scale": 0.5,
        "turnover_penalty": 0.2,
    }
    varied_hash_only = deepcopy(parameters)
    varied_hash_only["static_unused_marker"] = marker
    return {
        "candidate_id": candidate_id,
        "parameter_version": "ai_capex_token_static_noop_smoke_v1",
        "diagnostic_only": True,
        "parameters": varied_hash_only,
    }
