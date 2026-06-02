from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from api.score_pipeline.plugins.ai_capex_token_sector_tuning import (
    SECTOR_IDS,
    build_sector_component_tuning_report,
    render_sector_component_tuning_markdown,
)


REPORT_DIR = Path("reports/backtest/ai_capex_token_adaptive")
JSON_REPORT = REPORT_DIR / "sector_component_tuning_report.json"
MD_REPORT = REPORT_DIR / "sector_component_tuning_report.md"
CONFIG_PATH = Path("config/parameters/ai_capex_token_adaptive_tuning.yaml")


def test_sector_component_tuning_reports_exist_and_match_builder():
    assert JSON_REPORT.exists()
    assert MD_REPORT.exists()

    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    built = build_sector_component_tuning_report()

    assert report == built
    assert MD_REPORT.read_text(encoding="utf-8") == render_sector_component_tuning_markdown(built)


def test_component_weights_load_normalize_and_compose_under_existing_rules():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    selected = report["selected_candidate"]

    assert selected["score_component_only"] is True
    assert selected["target_weight_generation_allowed"] is False
    assert selected["order_generation_allowed"] is False
    assert set(selected["component_weights"]) == set(SECTOR_IDS)
    assert set(config["sector_component_weight_grid"]) >= set(SECTOR_IDS) | {"metadata"}
    for sector_id, component in selected["component_weights"].items():
        assert component["weights_sum"] == pytest.approx(1.0, abs=1e-5)
        assert component["diagnostic_only"] is True
        assert component["component_contribution"] <= component["contribution_cap"]
        assert selected["market_state_dampeners"]["max_component_contribution"] == component["contribution_cap"]


def test_penalty_bypass_controls_are_rejected_and_selected_penalties_are_preserved():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    selected = report["selected_candidate"]
    rejected = {item["candidate_id"]: item for item in report["rejected_candidates"]}

    assert selected["market_state_dampeners"]["penalties_preserved"] is True
    assert selected["market_state_dampeners"]["valuation_burden_penalty"] > 0
    assert selected["market_state_dampeners"]["data_quality_penalty"] > 0
    assert selected["market_state_dampeners"]["macro_stress_attenuation"] > 0
    assert selected["market_state_dampeners"]["turnover_pressure"] > 0
    assert rejected["valuation_penalty_zero_bypass"]["rejection_reason"] == "PENALTY_BYPASS_DETECTED"
    assert rejected["data_quality_penalty_zero_bypass"]["rejection_reason"] == "PENALTY_BYPASS_DETECTED"
    assert rejected["turnover_penalty_zero_bypass"]["rejection_reason"] == "PENALTY_BYPASS_DETECTED"


def test_macro_stress_cannot_redefine_scenario_and_inverse_cannot_dominate():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    selected = report["selected_candidate"]
    rejected = {item["candidate_id"]: item for item in report["rejected_candidates"]}
    inverse = selected["component_weights"]["inverse_hedge_diagnostic"]

    assert report["selection_policy"]["scenario_redefinition_allowed"] is False
    assert rejected["macro_stress_redefines_scenario"]["accepted"] is False
    assert rejected["macro_stress_redefines_scenario"]["scenario_redefinition_attempted"] is True
    assert inverse["user_review_required"] is True
    assert selected["metrics"]["inverse_share_of_total_score"] < 0.5
    assert rejected["inverse_dominance_control"]["rejection_reason"] == "INVERSE_DOMINANCE_DETECTED"


def test_reason_code_coverage_by_sector_and_required_explanations_exist():
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))
    selected = report["selected_candidate"]
    coverage = selected["reason_code_coverage_by_sector"]

    assert set(coverage) == set(SECTOR_IDS)
    for sector_id in ("bigtech_platform", "power_equipment", "semiconductor_hbm"):
        explanation = selected["component_weights"][sector_id]["score_explanation"]
        assert sector_id.split("_")[0] in explanation.lower() or sector_id == "semiconductor_hbm"
        assert coverage[sector_id]
        assert any("DAMPENER" in code for code in coverage[sector_id])
