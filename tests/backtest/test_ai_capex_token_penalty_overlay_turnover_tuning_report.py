from __future__ import annotations

import json
from pathlib import Path

from api.score_pipeline.plugins.ai_capex_token_penalty_tuning import (
    build_penalty_overlay_turnover_tuning_report,
    render_penalty_overlay_turnover_tuning_markdown,
)


REPORT_DIR = Path("reports/backtest/ai_capex_token_adaptive")
JSON_REPORT = REPORT_DIR / "penalty_overlay_turnover_tuning_report.json"
MD_REPORT = REPORT_DIR / "penalty_overlay_turnover_tuning_report.md"


def test_penalty_overlay_turnover_reports_exist_and_match_builder():
    assert JSON_REPORT.exists()
    assert MD_REPORT.exists()

    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    built = build_penalty_overlay_turnover_tuning_report()

    assert report == built
    assert MD_REPORT.read_text(encoding="utf-8") == render_penalty_overlay_turnover_tuning_markdown(built)


def test_poor_and_stale_data_cannot_increase_score_or_confidence():
    scenarios = _selected()["scenario_results"]

    assert scenarios["poor_data"]["score_contribution"] <= scenarios["base"]["score_contribution"]
    assert scenarios["stale_data"]["score_contribution"] <= scenarios["base"]["score_contribution"]
    assert scenarios["stale_data"]["confidence"] < scenarios["base"]["confidence"]
    assert "DATA_QUALITY_PENALTY_APPLIED" in scenarios["poor_data"]["reason_codes"]
    assert "STALE_DATA_CONFIDENCE_REDUCED" in scenarios["stale_data"]["reason_codes"]


def test_macro_stress_attenuates_risk_increasing_contribution():
    scenarios = _selected()["scenario_results"]

    assert scenarios["macro_stress"]["score_contribution"] <= scenarios["base"]["score_contribution"]
    assert scenarios["macro_stress"]["confidence"] < scenarios["base"]["confidence"]
    assert "MACRO_STRESS_ATTENUATION_APPLIED" in scenarios["macro_stress"]["reason_codes"]


def test_score_changes_are_capped_and_turnover_penalty_reduces_intensity():
    selected = _selected()
    scenarios = selected["scenario_results"]
    cap = selected["controls"]["max_score_change_per_period"]

    for scenario in scenarios.values():
        assert abs(scenario["score_change"]) <= cap
    assert scenarios["high_turnover"]["rebalancing_intensity"] < scenarios["no_turnover_penalty_reference"]["rebalancing_intensity"]
    assert "TURNOVER_PENALTY_REDUCED_INTENSITY" in scenarios["high_turnover"]["reason_codes"]


def test_reason_codes_include_penalty_effects_and_rejections_are_exact():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    selected = report["selected_candidate"]
    rejected = {item["candidate_id"]: item["rejection_reason"] for item in report["rejected_candidates"]}

    for expected in (
        "DATA_QUALITY_PENALTY_APPLIED",
        "STALE_DATA_CONFIDENCE_REDUCED",
        "MACRO_STRESS_ATTENUATION_APPLIED",
        "VALUATION_BURDEN_PENALTY_APPLIED",
        "TURNOVER_PENALTY_REDUCED_INTENSITY",
    ):
        assert expected in selected["reason_codes"]
    assert rejected["zero_penalty_return_chasing"] == "PENALTY_BYPASS_DETECTED"
    assert rejected["mdd_worsening_candidate"] == "MDD_WORSENED"
    assert rejected["turnover_spike_candidate"] == "TURNOVER_SPIKE_DETECTED"
    assert rejected["poor_data_risk_increase_candidate"] == "POOR_DATA_RISK_INCREASE_DETECTED"
    assert rejected["macro_stress_risk_amplifier"] == "MACRO_STRESS_RISK_AMPLIFICATION_DETECTED"
    assert rejected["high_valuation_momentum_chasing"] == "HIGH_VALUATION_MOMENTUM_CHASING_DETECTED"
    assert rejected["inverse_performance_dominance"] == "INVERSE_PERFORMANCE_DOMINANCE_DETECTED"


def test_diagnostic_mode_remains_zero_allocation_contribution():
    selected = _selected()

    assert selected["production_enabled"] is False
    assert selected["diagnostic_only"] is True
    assert selected["ready_for_allocation_contribution"] is False
    assert selected["allocation_contribution"] == 0.0


def _selected() -> dict:
    return json.loads(JSON_REPORT.read_text(encoding="utf-8"))["selected_candidate"]
