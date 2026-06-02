from __future__ import annotations

import json
from pathlib import Path

from api.score_pipeline.plugins.ai_capex_token_walk_forward_validation import (
    build_walk_forward_sensitivity_stress_report,
    render_walk_forward_sensitivity_stress_markdown,
)


REPORT_DIR = Path("reports/backtest/ai_capex_token_adaptive")
JSON_REPORT = REPORT_DIR / "walk_forward_sensitivity_stress_report.json"
MD_REPORT = REPORT_DIR / "walk_forward_sensitivity_stress_report.md"


def test_walk_forward_report_schema_and_builder_match():
    assert JSON_REPORT.exists()
    assert MD_REPORT.exists()

    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    built = build_walk_forward_sensitivity_stress_report()

    assert report == built
    assert MD_REPORT.read_text(encoding="utf-8") == render_walk_forward_sensitivity_stress_markdown(built)
    assert report["report_version"] == "ai_capex_token_walk_forward_sensitivity_stress_v1"
    assert report["mode"]["production_enabled"] is False
    assert report["mode"]["diagnostic_only"] is True


def test_memory_cycle_phase_metrics_and_full_window_gate_exist():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["memory_cycle_coverage"]["full_window_has_two_complete_cycles"] is True
    assert report["memory_cycle_coverage"]["complete_cycle_count"] >= 2
    assert set(report["memory_cycle_phase_metrics"]) == {"recovery", "normalization", "stress"}
    for metrics in report["memory_cycle_phase_metrics"].values():
        assert {"cost_adjusted_return", "max_drawdown", "score_turnover", "reason_codes"} <= set(metrics)


def test_walk_forward_rejected_candidates_and_sensitivity_perturbations_are_recorded():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["walk_forward_validation"]["method"] == "rolling_training_windows"
    assert report["walk_forward_validation"]["all_splits_have_history"] is True
    assert report["rejected_candidates"]
    assert any(item["gates"]["rejection_reason"] == "INSUFFICIENT_MEMORY_CYCLE_COVERAGE" for item in report["rejected_candidates"] if "gates" in item)
    perturbations = report["parameter_sensitivity"]["perturbations"]
    assert {item["parameter"] for item in perturbations} == {"lookback_months", "max_score_change_per_period"}
    assert all(item["stable"] is True for item in perturbations)
    assert report["parameter_sensitivity"]["sensitivity_failure"] is False


def test_cost_adjusted_metrics_tax_warning_and_stress_validation_exist():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["cost_adjusted_performance"]["supported"] is True
    assert "selected_candidate_cost_adjusted_return" in report["cost_adjusted_performance"]
    assert report["tax_adjusted_performance"]["supported"] is False
    assert report["tax_adjusted_performance"]["value"] is None
    assert "unsupported" in report["tax_adjusted_performance"]["warning"]
    assert report["stress_period_performance"]["stress_validation_failure"] is False
    assert report["stress_period_performance"]["stress_windows"][0]["drawdown_control_passed"] is True


def test_no_production_candidate_generated_and_reason_codes_are_covered():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["contribution_analysis"]["allocation_contribution"] == 0.0
    assert report["contribution_analysis"]["production_candidate_generated"] is False
    assert report["contribution_analysis"]["dominant_scenario_action_mapping"] is False
    assert report["turnover"]["allocation_turnover"] == 0.0
    assert report["turnover"]["turnover_control_active"] is True
    assert report["explanation_reason_code_coverage"]["all_required_sectors_covered"] is True
    assert report["explanation_reason_code_coverage"]["penalty_effects_covered"] is True
