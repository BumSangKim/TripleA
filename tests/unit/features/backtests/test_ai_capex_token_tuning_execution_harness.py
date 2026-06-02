from __future__ import annotations

import json
from pathlib import Path

from api.features.backtests.ai_capex_token_tuning_execution_test import (
    run_ai_capex_token_tuning_execution_test,
)


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token_tuning")


def test_tuning_harness_reports_candidate_and_unique_signature_counts():
    report = _run_report()

    assert report["candidate_count"] == 4
    assert report["unique_parameter_hash_count"] == 4
    assert report["unique_output_signature_count"] >= 2
    assert report["unique_metric_signature_count"] >= 2
    assert report["baseline_candidate_id"] == "baseline"
    assert report["status"] == "PASS_SYNTHETIC_ONLY"


def test_tuning_harness_keeps_every_candidate_diagnostic_only():
    report = _run_report()

    assert report["diagnostic_only"] is True
    assert report["production_ready"] is False
    assert all(result["candidate"]["diagnostic_only"] is True for result in report["candidates"])
    assert report["candidate_parameter_projection"] == {
        "scenario_smoothing_alpha": "scenario_probability_parameters.membership_strength"
    }


def test_tuning_harness_includes_memory_cycle_coverage_and_leakage_exclusion():
    report = _run_report()

    assert report["memory_cycle_coverage"]["status"] == "PASS_TWO_MEMORY_CYCLES"
    assert report["memory_cycle_coverage"]["distinct_cycle_count"] == 2
    assert report["leakage_check_passed"] is True
    assert all(
        "future.leakage_probe" in result["metrics"]["excluded_metric_keys"]
        for result in report["candidates"]
    )


def test_tuning_harness_result_is_deterministic():
    first = _run_report()
    second = _run_report()

    assert first == second


def test_tuning_harness_objective_is_composite_not_cagr_only():
    report = _run_report()

    for result in report["candidates"]:
        components = result["metrics"]["objective_components"]
        assert components["risk_adjusted_return"] is not None
        assert components["turnover_efficiency"] is not None
        assert components["cycle_stability"] is not None
        assert components["explainability"] is not None
        assert components["mdd_improvement"] is None
        assert "cagr" not in components


def _run_report() -> dict:
    candidate_grid = json.loads((FIXTURE_DIR / "candidate_grid_smoke.json").read_text(encoding="utf-8"))
    fixture = json.loads((FIXTURE_DIR / "synthetic_two_memory_cycles.json").read_text(encoding="utf-8"))
    return run_ai_capex_token_tuning_execution_test(
        candidate_grid=candidate_grid,
        snapshots=fixture["snapshots"],
    )
