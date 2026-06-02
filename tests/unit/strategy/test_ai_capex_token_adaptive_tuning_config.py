from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from api.score_pipeline.adaptive import AdaptiveNormalizationMethod, StaticValueAuditResult


PARAMETER_CONFIG_PATH = Path("config/parameters/ai_capex_token_adaptive_tuning.yaml")
BACKTEST_CONFIG_PATH = Path("config/backtest/ai_capex_token_adaptive_tuning.yaml")
CONSERVATIVE_FALLBACKS = {"NO_ACTION", "HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}
PARAMETER_GROUPS = {
    "adaptive_normalization_grid",
    "scenario_smoothing_grid",
    "sector_component_weight_grid",
    "market_state_dampening_grid",
}
FORBIDDEN_DIRECT_ACTION_TERMS = {
    "BUY",
    "SELL",
    "AUTO_EXECUTE",
    "LIVE_EXECUTE",
    "FORCE_REBALANCE",
    "INCREASE_RISK",
    "target_weight",
    "buy_threshold",
    "sell_threshold",
    "order_candidate",
}


def test_adaptive_tuning_parameter_config_loads():
    data = _load_parameter_config()

    assert data["fallback_policy"] == "REVIEW_REQUIRED"
    assert data["parameter_metadata"]["parameter_version"] == "ai_capex_token_adaptive_tuning_v0"


def test_adaptive_tuning_mode_keeps_production_closed():
    data = _load_parameter_config()
    mode = data["mode"]

    assert mode["production_enabled"] is False
    assert mode["diagnostic_only"] is True
    assert mode["approved"] is False
    assert mode["requires_two_memory_cycles"] is True
    assert mode["requires_backtest_pass"] is True
    assert mode["requires_walk_forward_pass"] is True


def test_parameter_metadata_is_unapproved_and_has_rollback_condition():
    metadata = _load_parameter_config()["parameter_metadata"]

    assert metadata["approved"] is False
    assert metadata["valid_from"] is None
    assert metadata["valid_to"] is None
    assert metadata["backtest_result"] is None
    assert metadata["walk_forward_result"] is None
    assert "rollback_condition" in metadata


def test_every_parameter_group_has_diagnostic_metadata():
    data = _load_parameter_config()

    for group in PARAMETER_GROUPS:
        metadata = data[group]["metadata"]
        assert metadata["approved"] is False
        assert metadata["diagnostic_only"] is True
        assert metadata["fallback_policy"] in CONSERVATIVE_FALLBACKS


def test_adaptive_normalization_methods_match_contract_enum():
    data = _load_parameter_config()
    allowed_methods = {method.value for method in AdaptiveNormalizationMethod}

    assert set(data["adaptive_normalization_grid"]["method"]) <= allowed_methods


def test_missing_parameter_policy_is_conservative():
    data = _load_parameter_config()

    assert data["fallback_policy"] in CONSERVATIVE_FALLBACKS
    for group in PARAMETER_GROUPS:
        assert data[group]["metadata"]["fallback_policy"] in CONSERVATIVE_FALLBACKS


def test_grid_values_are_not_direct_targets_or_buy_sell_thresholds():
    parameter_payload = yaml.safe_dump(_load_parameter_config())
    backtest_payload = yaml.safe_dump(_load_backtest_config())

    for term in FORBIDDEN_DIRECT_ACTION_TERMS:
        assert term not in parameter_payload
        assert term not in backtest_payload

    audit = StaticValueAuditResult.audit_mapping("adaptive_tuning_config", _load_parameter_config())
    assert audit.is_blocking is False
    assert audit.action_mapping_terms == ()


def test_backtest_config_requires_memory_cycle_gate_and_shadow_output_only():
    data = _load_backtest_config()

    assert data["mode"]["production_enabled"] is False
    assert data["mode"]["diagnostic_only"] is True
    assert data["mode"]["approved"] is False
    assert data["memory_cycle_gate"]["required"] is True
    assert data["memory_cycle_gate"]["minimum_complete_cycles"] == 2
    assert data["memory_cycle_gate"]["fail_status"] == "INSUFFICIENT_MEMORY_CYCLE_COVERAGE"
    assert data["output"]["shadow_candidate_only"] is True
    assert data["output"]["automatic_production_promotion_allowed"] is False
    assert data["output"]["order_generation_allowed"] is False


def _load_parameter_config() -> dict[str, Any]:
    assert PARAMETER_CONFIG_PATH.exists()
    return yaml.safe_load(PARAMETER_CONFIG_PATH.read_text(encoding="utf-8"))


def _load_backtest_config() -> dict[str, Any]:
    assert BACKTEST_CONFIG_PATH.exists()
    return yaml.safe_load(BACKTEST_CONFIG_PATH.read_text(encoding="utf-8"))
