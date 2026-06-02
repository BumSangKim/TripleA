from __future__ import annotations

import json
from pathlib import Path

from api.features.backtests.ai_capex_token_tuning_execution_test import (
    run_ai_capex_token_tuning_execution_test,
)


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token_tuning")


def test_synthetic_two_cycle_tuning_changes_outputs_and_selects_candidate():
    report = _report()

    assert report["unique_output_signature_count"] >= 2
    assert report["unique_metric_signature_count"] >= 2
    assert report["selected_candidate_id"] is not None
    assert report["rejected_candidates"]
    assert report["status"] != "FAIL_NOOP_TUNING"
    assert report["no_op_tuning_detected"] is False


def test_selected_candidate_has_objective_breakdown():
    report = _report()

    selected = report["selected_candidate_id"]
    objective = report["objective_breakdown"][selected]

    assert objective["risk_adjusted_return"] is not None
    assert objective["turnover_efficiency"] is not None
    assert objective["cycle_stability"] is not None
    assert objective["parameter_robustness"] is not None
    assert objective["explainability"] is not None
    assert objective["penalties"]["cagr_only_penalty"] == 0.0


def test_rejected_candidates_include_diagnostic_reason():
    report = _report()

    assert any(
        "OBJECTIVE_BELOW_BASELINE_DIAGNOSTIC_REJECTED" in rejected["reject_reasons"]
        for rejected in report["rejected_candidates"]
    )
    assert all(result["candidate"]["diagnostic_only"] is True for result in report["candidates"])
    assert report["production_ready"] is False


def _report() -> dict:
    candidate_grid = json.loads((FIXTURE_DIR / "candidate_grid_smoke.json").read_text(encoding="utf-8"))
    fixture = json.loads((FIXTURE_DIR / "synthetic_two_memory_cycles.json").read_text(encoding="utf-8"))
    return run_ai_capex_token_tuning_execution_test(
        candidate_grid=candidate_grid,
        snapshots=fixture["snapshots"],
    )
