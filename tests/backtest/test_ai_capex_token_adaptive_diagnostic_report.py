from __future__ import annotations

import json
from pathlib import Path

import yaml

from api.score_pipeline.plugins.ai_capex_token_diagnostic_backtest import (
    build_ai_capex_token_diagnostic_report,
    render_diagnostic_markdown,
)


REPORT_DIR = Path("reports/backtest/ai_capex_token_adaptive")
DIAGNOSTIC_JSON = REPORT_DIR / "diagnostic_report.json"
DIAGNOSTIC_MD = REPORT_DIR / "diagnostic_report.md"
BASELINE_JSON = REPORT_DIR / "baseline_report.json"
CONFIG_PATH = Path("config/backtest/ai_capex_token_adaptive_diagnostic.yaml")
REQUIRED_PERIOD_FIELDS = {
    "adaptive_normalized_features",
    "scenario_distribution",
    "dominant_scenario",
    "sector_component_diagnostics",
    "market_state_dampeners",
    "score_turnover",
    "scenario_turnover",
    "reason_codes",
    "data_quality_by_period",
    "memory_cycle_phase",
    "calibration_window_metadata",
}


def test_diagnostic_reports_exist_and_match_builder():
    assert DIAGNOSTIC_JSON.exists()
    assert DIAGNOSTIC_MD.exists()

    report = json.loads(DIAGNOSTIC_JSON.read_text(encoding="utf-8"))
    built = build_ai_capex_token_diagnostic_report()

    assert report == built
    assert DIAGNOSTIC_MD.read_text(encoding="utf-8") == render_diagnostic_markdown(built)


def test_diagnostic_fields_exist_for_every_period():
    report = json.loads(DIAGNOSTIC_JSON.read_text(encoding="utf-8"))

    for period in report["periods"]:
        assert REQUIRED_PERIOD_FIELDS <= set(period)
        assert period["parameter_version"] == "ai_capex_token_adaptive_tuning_v0"
        assert period["model_version"] == "ai_capex_token_adaptive_shadow_v0"
        assert period["dominant_scenario_explanation_only"] is True
        assert sum(period["scenario_distribution"].values()) == 1.0


def test_final_allocation_and_return_equal_baseline_when_contribution_zero():
    report = json.loads(DIAGNOSTIC_JSON.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))

    assert report["diagnostic_result"]["allocation_contribution"] == 0.0
    assert report["diagnostic_result"]["final_allocation_changed"] is False
    assert report["diagnostic_result"]["final_value"] == baseline["baselines"][0]["final_value"]
    assert report["diagnostic_result"]["cost_adjusted_return"] == baseline["baselines"][0]["metrics"]["cost_adjusted_return"]


def test_data_quality_warnings_and_reason_code_frequency_are_carried_forward():
    report = json.loads(DIAGNOSTIC_JSON.read_text(encoding="utf-8"))

    assert report["reason_code_frequency"]["ADAPTIVE_DIAGNOSTIC_ONLY"] == len(report["periods"])
    low_quality_periods = [period for period in report["periods"] if period["data_quality_by_period"] < 0.8]
    assert low_quality_periods
    assert "LOW_DATA_QUALITY_REVIEW_REQUIRED" in low_quality_periods[0]["warnings"]


def test_dominant_scenario_is_not_used_for_allocation_and_future_outcome_is_analysis_only():
    report = json.loads(DIAGNOSTIC_JSON.read_text(encoding="utf-8"))
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["diagnostic"]["use_future_outcomes_for_signal"] is False
    assert report["future_outcome_comparison"]["analysis_only"] is True
    assert report["future_outcome_comparison"]["not_used_for_signal_calculation"] is True
    for period in report["periods"]:
        assert period["future_outcome_comparison"]["analysis_only"] is True
        assert period["future_outcome_comparison"]["not_used_for_signal_calculation"] is True
        for diagnostic in period["sector_component_diagnostics"].values():
            assert diagnostic["component_contribution"] == 0.0
            assert diagnostic["diagnostic_only"] is True
