from __future__ import annotations

import pytest

from api.features.backtests.sector_component_portfolios import (
    SectorComponentSectorPortfolio,
    SectorPortfolioAsset,
    validate_weight_sum,
)


def portfolio(enabled: bool = True) -> SectorComponentSectorPortfolio:
    return SectorComponentSectorPortfolio(
        sector_id="SEMICONDUCTOR",
        display_name="Semiconductor",
        portfolio_id="sector_semiconductor_current_v1",
        enabled=enabled,
        display_order=10,
        assets=(
            SectorPortfolioAsset("SMH", 0.5, "primary_proxy"),
            SectorPortfolioAsset("SOXX", 0.5, "secondary_proxy"),
        ),
        reason_codes=("CURRENT_TAXONOMY_ASSET_FIXTURE",),
    )


def test_valid_portfolio_creation() -> None:
    result = portfolio()

    assert result.sector_id == "SEMICONDUCTOR"
    assert result.asset_count == 2
    assert result.semantics == "diagnostic_sector_sleeve_fixture"


def test_weight_sum_mismatch_fails() -> None:
    with pytest.raises(ValueError, match="sum to 1.0"):
        SectorComponentSectorPortfolio(
            sector_id="POWER_GRID",
            display_name="Power Grid",
            portfolio_id="sector_power_grid_current_v1",
            assets=(SectorPortfolioAsset("XLU", 0.8),),
        )
    with pytest.raises(ValueError, match="sum to 1.0"):
        validate_weight_sum((SectorPortfolioAsset("XLU", 0.8),))


def test_empty_assets_fail() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        SectorComponentSectorPortfolio(
            sector_id="BATTERY",
            display_name="Battery",
            portfolio_id="sector_battery_current_v1",
            assets=(),
        )


def test_disabled_portfolio_is_valid_contract_state() -> None:
    result = portfolio(enabled=False)

    assert result.enabled is False
    assert result.asset_count == 2


def test_asset_code_is_normalized_and_weight_is_non_negative() -> None:
    asset = SectorPortfolioAsset("smh", 0.5, "primary_proxy")

    assert asset.asset_code == "SMH"
    with pytest.raises(ValueError, match="non-negative"):
        SectorPortfolioAsset("SMH", -0.1)


def test_to_dict_serialization() -> None:
    payload = portfolio().to_dict()

    assert payload["sector_id"] == "SEMICONDUCTOR"
    assert payload["assets"][0]["asset_code"] == "SMH"
    assert payload["assets"][0]["weight"] == 0.5
    assert payload["assets"][0]["role"] == "primary_proxy"
    assert "category" in payload["assets"][0]
    assert payload["reason_codes"] == ["CURRENT_TAXONOMY_ASSET_FIXTURE"]
