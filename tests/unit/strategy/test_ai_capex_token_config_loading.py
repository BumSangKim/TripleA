from __future__ import annotations

from pathlib import Path

import yaml


CONFIG_PATH = Path("config/scoring/ai_capex_token.yaml")
REQUIRED_GROUPS = {
    "normalization_parameters",
    "scenario_probability_parameters",
    "sector_component_weights",
    "macro_overlay_weights",
    "data_quality_policy",
    "production_gate",
}
CONSERVATIVE_FALLBACKS = {"NO_ACTION", "HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}
RISK_INCREASING_TERMS = {
    "BUY",
    "INCREASE_RISK",
    "INCREASE_SATELLITE_WEIGHT",
    "FORCE_REBALANCE",
    "AUTO_EXECUTE",
    "LIVE_EXECUTE",
}


def test_ai_capex_token_yaml_parses():
    data = _load_config()

    assert data["enabled"] is False
    assert data["production_enabled"] is False
    assert data["diagnostic_only"] is True
    assert data["parameter_metadata"]["approved"] is False


def test_production_gate_is_closed_by_default():
    data = _load_config()

    assert data["requires_backtest_pass"] is True
    assert data["requires_walk_forward_pass"] is True
    assert data["requires_user_approval_for_production"] is True
    assert data["production_gate"]["default_state"] == "diagnostic_only"


def test_all_parameter_groups_have_metadata():
    data = _load_config()

    for group in REQUIRED_GROUPS:
        assert "metadata" in data[group], group
        assert data[group]["metadata"]["approved"] is False
        assert data[group]["metadata"]["fallback_policy"] in CONSERVATIVE_FALLBACKS


def test_missing_required_parameters_have_conservative_fallback_policy():
    data = _load_config()

    assert data["fallback_policy"] in CONSERVATIVE_FALLBACKS
    assert data["data_quality_policy"]["missing_input_action"] == "REVIEW_REQUIRED"
    assert data["data_quality_policy"]["stale_input_action"] == "HOLD"
    assert data["data_quality_policy"]["unavailable_at_decision_time_action"] == "REVIEW_REQUIRED"
    assert data["data_quality_policy"]["risk_increase_on_error_allowed"] is False


def test_no_risk_increasing_defaults_are_present():
    data = _load_config()
    payload = yaml.safe_dump(data).upper()

    for term in RISK_INCREASING_TERMS:
        assert term not in payload


def test_unapproved_strategy_parameters_are_not_production_values():
    data = _load_config()

    assert data["normalization_parameters"]["token_change_bounds"] is None
    assert data["sector_component_weights"]["inverse_hedge"]["diagnostic_only"] is True
    assert data["sector_component_weights"]["inverse_hedge"]["requires_existing_hedge_policy"] is True
    assert data["test_parameters"]["metadata"]["scope"] == "unit_tests_only"


def _load_config() -> dict:
    assert CONFIG_PATH.exists()
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
