from __future__ import annotations

import json
from pathlib import Path

from api.features.backtests.ai_capex_token_tuning_execution_test import (
    run_ai_capex_token_tuning_execution_test,
)


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token_tuning")


def test_high_return_marker_cannot_override_mdd_worsening_penalty():
    report = _report(_objective_candidate_grid())
    rejected = {item["candidate_id"]: item["reject_reasons"] for item in report["rejected_candidates"]}

    assert "high_return_bad_mdd" in rejected
    assert "MDD_WORSENING_DIAGNOSTIC_PENALTY" in rejected["high_return_bad_mdd"]
    assert report["selected_candidate_id"] != "high_return_bad_mdd"
    assert "synthetic_total_return" not in report["objective_breakdown"]["high_return_bad_mdd"]


def test_turnover_penalty_is_reflected_in_objective_breakdown():
    report = _report(_objective_candidate_grid())
    low = report["objective_breakdown"]["baseline"]["penalties"]["turnover_penalty"]
    high = report["objective_breakdown"]["high_turnover"]["penalties"]["turnover_penalty"]

    assert high > low
    assert report["objective_breakdown"]["high_turnover"]["turnover_efficiency"] < report["objective_breakdown"]["baseline"]["turnover_efficiency"]


def test_one_cycle_only_candidate_is_penalized_and_rejected():
    report = _report(_objective_candidate_grid())
    rejected = {item["candidate_id"]: item["reject_reasons"] for item in report["rejected_candidates"]}

    assert "one_cycle_only" in rejected
    assert "ONE_CYCLE_ONLY_DIAGNOSTIC_PENALTY" in rejected["one_cycle_only"]
    assert report["objective_breakdown"]["one_cycle_only"]["penalties"]["one_cycle_only_penalty"] > 0


def test_objective_breakdown_is_composite_and_non_empty():
    report = _report(_objective_candidate_grid())

    for breakdown in report["objective_breakdown"].values():
        assert breakdown
        assert set(breakdown) >= {
            "mdd_improvement",
            "risk_adjusted_return",
            "turnover_efficiency",
            "cycle_stability",
            "parameter_robustness",
            "explainability",
            "penalties",
        }
        assert "cagr" not in breakdown
        assert "total_return" not in breakdown


def _report(candidate_grid: dict) -> dict:
    fixture = json.loads((FIXTURE_DIR / "synthetic_two_memory_cycles.json").read_text(encoding="utf-8"))
    return run_ai_capex_token_tuning_execution_test(candidate_grid=candidate_grid, snapshots=fixture["snapshots"])


def _objective_candidate_grid() -> dict:
    return {
        "metadata": {
            "fixture_id": "ai_capex_token_objective_rules_grid_v1",
            "diagnostic_only": True,
            "production_enabled": False,
            "approved": False,
        },
        "candidates": [
            _candidate("baseline", scenario_smoothing_alpha=0.5, turnover_penalty=0.2),
            _candidate(
                "high_return_bad_mdd",
                scenario_smoothing_alpha=0.8,
                turnover_penalty=0.1,
                diagnostic_mdd_worsening=1.0,
                synthetic_total_return=10.0,
            ),
            _candidate("high_turnover", scenario_smoothing_alpha=0.8, turnover_penalty=0.95),
            _candidate(
                "one_cycle_only",
                scenario_smoothing_alpha=0.8,
                turnover_penalty=0.1,
                diagnostic_active_cycle_count=1,
            ),
        ],
    }


def _candidate(candidate_id: str, **overrides) -> dict:
    parameters = {
        "normalization_strength": 0.5,
        "scenario_smoothing_alpha": 0.5,
        "sector_component_scale": 0.5,
        "turnover_penalty": 0.2,
    }
    parameters.update(overrides)
    return {
        "candidate_id": candidate_id,
        "parameter_version": "ai_capex_token_objective_rules_smoke_v1",
        "diagnostic_only": True,
        "parameters": parameters,
    }
