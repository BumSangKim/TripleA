from __future__ import annotations

import json
from pathlib import Path

from api.score_pipeline.plugins.ai_capex_token_normalization_tuning import (
    build_normalization_smoothing_tuning_report,
    render_normalization_smoothing_tuning_markdown,
)


REPORT_DIR = Path("reports/backtest/ai_capex_token_adaptive")
JSON_REPORT = REPORT_DIR / "normalization_smoothing_tuning_report.json"
MD_REPORT = REPORT_DIR / "normalization_smoothing_tuning_report.md"


def test_normalization_smoothing_reports_exist_and_match_builder():
    assert JSON_REPORT.exists()
    assert MD_REPORT.exists()

    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    built = build_normalization_smoothing_tuning_report()

    assert report == built
    assert MD_REPORT.read_text(encoding="utf-8") == render_normalization_smoothing_tuning_markdown(built)


def test_every_candidate_uses_only_past_calibration_data_and_records_fit_windows():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["candidate_count"] == len(report["evaluated_candidates"])
    for candidate in report["evaluated_candidates"]:
        assert candidate["gates"]["leakage_safe"] is True
        assert candidate["gates"]["uses_only_past_calibration_data"] is True
        assert candidate["parameter_version"] == "ai_capex_token_adaptive_tuning_v0"
        assert candidate["model_version"] == "ai_capex_token_adaptive_shadow_v0"
        assert candidate["fit_windows"]
        for window in candidate["fit_windows"]:
            assert window["uses_only_past_calibration_data"] is True
            assert window["fit_end_date"] <= window["decision_date"]
            assert window["available_at_cutoff"] <= window["decision_date"]
            assert window["observation_count"] >= window["min_observations"]


def test_candidate_with_fewer_than_two_memory_cycles_is_rejected():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    control = report["rejection_controls"][0]

    assert control["candidate_id"] == "negative_control_fewer_than_two_memory_cycles"
    assert control["gates"]["complete_memory_cycles"] == 1
    assert control["gates"]["accepted"] is False
    assert control["gates"]["rejection_reason"] == "INSUFFICIENT_MEMORY_CYCLE_COVERAGE"


def test_selected_candidate_is_not_chosen_by_cagr_alone():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    selected = report["selected_candidate"]

    assert selected is not None
    assert selected["diagnostic_selected"] is True
    assert selected["production_enabled"] is False
    assert selected["allocation_contribution"] == 0.0
    assert selected["analysis_only_cagr_rank"] > 1
    assert "cagr_analysis_only_after_gates" == report["selection_criteria_order"][-1]
    assert "before CAGR" in selected["selection_reason"]


def test_sensitivity_turnover_and_detection_delay_metrics_exist():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["sensitivity_summary"]["exists"] is True
    assert report["sensitivity_summary"]["by_method"]
    for candidate in report["evaluated_candidates"]:
        assert "scenario_turnover" in candidate["metrics"]
        assert "score_turnover" in candidate["metrics"]
        assert "detection_delay_periods" in candidate["metrics"]
        assert "calibration_stability" in candidate["metrics"]
        assert "lookback_sensitivity_bucket" in candidate["sensitivity"]
