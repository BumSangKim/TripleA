from __future__ import annotations

from api.features.backtests.schemas import SectorComponentUiMetadataResponse
from api.features.backtests.sector_component_config import SectorComponentBacktestConfig, SectorComponentWeightSet
from api.features.backtests.sector_component_portfolios import SectorComponentSectorPortfolio, SectorPortfolioAsset
from api.features.backtests.sector_component_ui_metadata import build_sector_component_ui_metadata


def config() -> SectorComponentBacktestConfig:
    return SectorComponentBacktestConfig(
        parameter_version="p1",
        model_version="m1",
        enabled_components=("trade",),
        component_weight_grid=(SectorComponentWeightSet("baseline", {"trade": 1.0}),),
        rebalance_frequency="monthly",
        decision_lag_days=1,
        transaction_cost_bps=0.0,
        tax_assumption_enabled=False,
        stress_periods=(),
        required_metrics=("total_return",),
        fallback_policy="REVIEW_REQUIRED",
    )


def portfolio(
    sector_id: str,
    display_name: str,
    display_order: int,
    *,
    enabled: bool = True,
    warnings: tuple[str, ...] = (),
) -> SectorComponentSectorPortfolio:
    return SectorComponentSectorPortfolio(
        sector_id=sector_id,
        display_name=display_name,
        portfolio_id=f"sector_{sector_id.lower()}_current_v1",
        display_order=display_order,
        enabled=enabled,
        assets=(SectorPortfolioAsset(f"{sector_id}_ETF", 1.0),),
        reason_codes=("CURRENT_TAXONOMY_ASSET_FIXTURE",),
        warnings=warnings,
    )


def test_all_option_always_exists() -> None:
    metadata = build_sector_component_ui_metadata(config(), [])

    assert metadata.allSectorOption.value == "ALL"
    assert metadata.allSectorOption.sectorScope.mode == "all"


def test_sector_options_are_sorted_by_enabled_portfolio_order() -> None:
    metadata = build_sector_component_ui_metadata(
        config(),
        (
            portfolio("BATTERY", "Battery", 30),
            portfolio("SEMICONDUCTOR", "Semiconductor", 10),
            portfolio("POWER_GRID", "Power Grid", 20),
        ),
    )

    assert [option.sectorId for option in metadata.sectorOptions] == ["SEMICONDUCTOR", "POWER_GRID", "BATTERY"]


def test_disabled_portfolio_is_excluded() -> None:
    metadata = build_sector_component_ui_metadata(
        config(),
        (
            portfolio("SEMICONDUCTOR", "Semiconductor", 10),
            portfolio("BATTERY", "Battery", 20, enabled=False),
        ),
    )

    assert [option.sectorId for option in metadata.sectorOptions] == ["SEMICONDUCTOR"]


def test_warning_is_passed_to_option() -> None:
    metadata = build_sector_component_ui_metadata(
        config(),
        (
            portfolio(
                "SEMICONDUCTOR",
                "Semiconductor",
                10,
                warnings=("ASSET_NOT_IN_INVESTMENT_UNIVERSE_REVIEW_REQUIRED:SOXX",),
            ),
        ),
    )

    option = metadata.sectorOptions[0]
    assert option.warnings[0]["code"] == "ASSET_NOT_IN_INVESTMENT_UNIVERSE_REVIEW_REQUIRED"
    assert "REVIEW_REQUIRED" in option.reasonCodes


def test_reference_assets_are_exposed_for_ui_diagnostics() -> None:
    metadata = build_sector_component_ui_metadata(
        config(),
        (
            SectorComponentSectorPortfolio(
                sector_id="SEMICONDUCTOR",
                display_name="Semiconductor",
                portfolio_id="sector_semiconductor_trade_reference_v1",
                display_order=10,
                assets=(
                    SectorPortfolioAsset(
                        "NVDA",
                        1.0,
                        role="ai_accelerator_leader",
                        name="NVIDIA",
                        category="overseas_stock",
                        market="US",
                        exchange="NASDAQ",
                        currency="USD",
                        risk_tags=("single_name_volatility",),
                    ),
                ),
            ),
        ),
    )

    asset = metadata.sectorOptions[0].assets[0]
    assert asset["assetCode"] == "NVDA"
    assert asset["category"] == "overseas_stock"
    assert asset["weight"] == 1.0


def test_parameter_and_model_versions_are_included() -> None:
    metadata = build_sector_component_ui_metadata(config(), ())

    assert metadata.parameterVersion == "p1"
    assert metadata.modelVersion == "m1"
    assert metadata.reasonCodes == ["SECTOR_COMPONENT_UI_METADATA_BUILT"]


def test_response_schema_validate_possible() -> None:
    metadata = build_sector_component_ui_metadata(config(), (portfolio("POWER_GRID", "Power Grid", 20),))
    validated = SectorComponentUiMetadataResponse.model_validate(metadata.model_dump())

    assert validated.ok is True
    assert validated.sectorOptions[0].value == "POWER_GRID"
