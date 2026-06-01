from __future__ import annotations

import copy

import pytest

from api.features.backtests.sector_component_portfolios import (
    enabled_sector_component_portfolios,
    load_sector_component_sector_portfolios,
    parse_sector_component_sector_portfolios,
)


def taxonomy() -> dict:
    return {
        "sectors": {
            "SEMICONDUCTOR": {"assets": ["SMH", "SOXX", "NVDA"]},
            "POWER_GRID": {"assets": ["XLU"]},
            "BATTERY": {"assets": ["LIT"]},
        }
    }


def investment_universe(asset_codes=("SMH",)) -> dict:
    return {
        "universes": {
            "default_global": {
                "assets": [{"asset_code": code} for code in asset_codes],
            }
        }
    }


def raw_config() -> dict:
    return {
        "portfolios": [
            {
                "sector_id": "SEMICONDUCTOR",
                "display_name": "Semiconductor",
                "portfolio_id": "sector_semiconductor_current_v1",
                "enabled": True,
                "display_order": 10,
                "assets": [
                    {"asset_code": "SMH", "weight": 0.5, "role": "primary_proxy"},
                    {"asset_code": "SOXX", "weight": 0.5, "role": "secondary_proxy"},
                ],
                "reason_codes": ["CURRENT_TAXONOMY_ASSET_FIXTURE"],
            },
            {
                "sector_id": "POWER_GRID",
                "display_name": "Power Grid",
                "portfolio_id": "sector_power_grid_current_v1",
                "enabled": True,
                "display_order": 20,
                "assets": [{"asset_code": "XLU", "weight": 1.0, "role": "primary_proxy"}],
            },
            {
                "sector_id": "BATTERY",
                "display_name": "Battery",
                "portfolio_id": "sector_battery_current_v1",
                "enabled": True,
                "display_order": 30,
                "assets": [{"asset_code": "LIT", "weight": 1.0, "role": "primary_proxy"}],
            },
        ],
    }


def test_default_config_loads_three_current_sector_portfolios() -> None:
    portfolios = load_sector_component_sector_portfolios()

    assert [item.sector_id for item in portfolios] == ["SEMICONDUCTOR", "POWER_GRID", "BATTERY"]
    assert len(enabled_sector_component_portfolios(portfolios)) == 3


def test_semiconductor_asset_weights_sum_to_one() -> None:
    portfolios = load_sector_component_sector_portfolios()
    semiconductor = next(item for item in portfolios if item.sector_id == "SEMICONDUCTOR")

    assert sum(asset.weight for asset in semiconductor.assets) == 1.0
    assert semiconductor.portfolio_id == "sector_semiconductor_trade_reference_v1"
    assert semiconductor.asset_count == 18
    assert semiconductor.assets[0].asset_code == "000660"
    assert semiconductor.assets[0].category == "domestic_stock"


def test_trade_reference_category_weights_match_reference_sheet() -> None:
    portfolios = load_sector_component_sector_portfolios()
    expected = {
        "SEMICONDUCTOR": {"domestic_stock": 0.30, "domestic_etf": 0.20, "overseas_stock": 0.30, "overseas_etf": 0.20},
        "POWER_GRID": {"domestic_stock": 0.35, "domestic_etf": 0.25, "overseas_stock": 0.25, "overseas_etf": 0.15},
        "BATTERY": {"domestic_stock": 0.35, "domestic_etf": 0.20, "overseas_stock": 0.25, "overseas_etf": 0.20},
    }

    for portfolio in portfolios:
        category_weights: dict[str, float] = {}
        for asset in portfolio.assets:
            category_weights[asset.category or "UNKNOWN"] = category_weights.get(asset.category or "UNKNOWN", 0.0) + asset.weight
        assert category_weights == pytest.approx(expected[portfolio.sector_id])


def test_trade_reference_format_is_supported() -> None:
    raw = {
        "portfolio_version": "test_reference_v1",
        "classification": "trade_reference_model_portfolio",
        "global_policy": {"automatic_execution_allowed": False, "base_weights_must_sum_to": 1.0},
        "sectors": [
            {
                "sector_id": "SEMICONDUCTOR",
                "display_name": "Semiconductor",
                "portfolio_id": "sector_semiconductor_reference_v1",
                "assets": [
                    {
                        "asset_code": "NVDA",
                        "name": "NVIDIA",
                        "category": "overseas_stock",
                        "market": "US",
                        "exchange": "NASDAQ",
                        "currency": "USD",
                        "role": "ai_accelerator_leader",
                        "min_weight": 0.0,
                        "base_weight": 1.0,
                        "max_weight": 1.0,
                        "risk_tags": ["single_name_volatility"],
                    }
                ],
            }
        ],
    }

    portfolios = parse_sector_component_sector_portfolios(
        raw,
        taxonomy_raw=taxonomy(),
        investment_universe_raw=investment_universe(asset_codes=("NVDA",)),
    )

    assert portfolios[0].portfolio_id == "sector_semiconductor_reference_v1"
    assert portfolios[0].assets[0].weight == 1.0
    assert portfolios[0].assets[0].risk_tags == ("single_name_volatility",)
    assert "TRADE_REFERENCE_MODEL_PORTFOLIO" in portfolios[0].reason_codes


def test_unknown_sector_fails() -> None:
    raw = raw_config()
    raw["portfolios"][0]["sector_id"] = "UNKNOWN"

    with pytest.raises(ValueError, match="unknown sector_id"):
        parse_sector_component_sector_portfolios(raw, taxonomy_raw=taxonomy(), investment_universe_raw=investment_universe())


def test_asset_not_in_taxonomy_fails() -> None:
    raw = raw_config()
    raw["portfolios"][0]["assets"][0]["asset_code"] = "QQQ"

    with pytest.raises(ValueError, match="asset not in taxonomy"):
        parse_sector_component_sector_portfolios(raw, taxonomy_raw=taxonomy(), investment_universe_raw=investment_universe())


def test_asset_not_in_investment_universe_is_review_warning() -> None:
    portfolios = parse_sector_component_sector_portfolios(
        raw_config(),
        taxonomy_raw=taxonomy(),
        investment_universe_raw=investment_universe(asset_codes=("SMH",)),
    )
    warnings = [warning for portfolio in portfolios for warning in portfolio.warnings]

    assert "ASSET_NOT_IN_INVESTMENT_UNIVERSE_REVIEW_REQUIRED:SOXX" in warnings
    assert "ASSET_NOT_IN_INVESTMENT_UNIVERSE_REVIEW_REQUIRED:XLU" in warnings
    assert "ASSET_NOT_IN_INVESTMENT_UNIVERSE_REVIEW_REQUIRED:LIT" in warnings


def test_disabled_portfolio_is_hidden_by_enabled_helper() -> None:
    raw = copy.deepcopy(raw_config())
    raw["portfolios"][1]["enabled"] = False
    portfolios = parse_sector_component_sector_portfolios(
        raw,
        taxonomy_raw=taxonomy(),
        investment_universe_raw=investment_universe(asset_codes=("SMH", "SOXX", "XLU", "LIT")),
    )

    assert [item.sector_id for item in enabled_sector_component_portfolios(portfolios)] == ["SEMICONDUCTOR", "BATTERY"]
