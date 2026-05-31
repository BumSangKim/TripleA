from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from api.features.backtests.sector_component_config import (
    DEFAULT_CONFIG_PATH,
    SectorComponentConfigError,
    load_sector_component_backtest_config,
    parse_sector_component_backtest_config,
)


def base_config() -> dict:
    return {
        "parameter_version": "sector_component_backtest_v0",
        "model_version": "sector_component_backtest_model_v0",
        "enabled_components": ["trade", "demand", "supply", "relative_strength"],
        "component_weight_grid": [
            {
                "parameter_set_id": "balanced",
                "weights": {
                    "trade": 0.25,
                    "demand": 0.25,
                    "supply": 0.25,
                    "relative_strength": 0.25,
                },
            }
        ],
        "rebalance_frequency": "monthly",
        "decision_lag_days": 1,
        "transaction_cost_bps": 10.0,
        "tax_assumption_enabled": False,
        "stress_periods": [{"name": "stress", "start_date": "2022-01-01", "end_date": "2022-12-31"}],
        "required_metrics": ["total_return", "max_drawdown"],
        "fallback_policy": "REVIEW_REQUIRED",
    }


def test_loads_repository_config() -> None:
    config = load_sector_component_backtest_config(DEFAULT_CONFIG_PATH)

    assert config.parameter_version == "sector_component_backtest_v0"
    assert config.model_version == "sector_component_backtest_model_v0"
    assert config.fallback_policy == "REVIEW_REQUIRED"
    assert config.component_weight_grid[0].weights["trade"] == 0.25


def test_can_load_from_yaml_file(tmp_path: Path) -> None:
    path = tmp_path / "sector_component_backtest.yaml"
    path.write_text(yaml.safe_dump(base_config()), encoding="utf-8")

    config = load_sector_component_backtest_config(path)

    assert config.parameter_version == "sector_component_backtest_v0"
    assert config.model_version == "sector_component_backtest_model_v0"


def test_missing_required_parameter_is_blocked() -> None:
    raw = base_config()
    raw.pop("parameter_version")

    with pytest.raises(SectorComponentConfigError, match="parameter_version"):
        parse_sector_component_backtest_config(raw)


def test_weight_grid_sum_is_not_auto_normalized() -> None:
    raw = base_config()
    raw["component_weight_grid"][0]["weights"]["trade"] = 0.30

    with pytest.raises(SectorComponentConfigError, match="sum to 1.0"):
        parse_sector_component_backtest_config(raw)


def test_unknown_component_name_is_review_warning() -> None:
    raw = base_config()
    raw["enabled_components"] = ["trade", "unknown_component"]
    raw["component_weight_grid"][0]["weights"] = {"trade": 0.5, "unknown_component": 0.5}

    config = parse_sector_component_backtest_config(raw)

    assert config.validation_warnings[0].code == "UNKNOWN_COMPONENT_REVIEW_REQUIRED"
    assert config.validation_warnings[0].fallback_state == "REVIEW_REQUIRED"


def test_weight_for_disabled_component_is_blocked() -> None:
    raw = base_config()
    raw["component_weight_grid"][0]["weights"]["not_enabled"] = 0.0

    with pytest.raises(SectorComponentConfigError, match="disabled components"):
        parse_sector_component_backtest_config(raw)


def test_fallback_policy_must_be_conservative() -> None:
    raw = base_config()
    raw["fallback_policy"] = "BUY_MORE"

    with pytest.raises(SectorComponentConfigError, match="fallback_policy"):
        parse_sector_component_backtest_config(raw)


def test_config_contract_has_no_sector_specific_weights() -> None:
    config = load_sector_component_backtest_config(DEFAULT_CONFIG_PATH)
    raw_text = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")

    assert "sector_weights" not in raw_text
    assert "SEMICONDUCTOR:" not in raw_text
    assert "BATTERY:" not in raw_text
    assert all(set(item.weights) == set(config.enabled_components) for item in config.component_weight_grid)

