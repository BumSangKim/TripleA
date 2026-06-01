from __future__ import annotations

from typing import Any, Mapping, Sequence

from api.features.backtests.schemas import SectorComponentUiMetadataResponse
from api.features.backtests.sector_component_portfolios import (
    SectorComponentSectorPortfolio,
    enabled_sector_component_portfolios,
)


def build_sector_component_ui_metadata(
    config: Any,
    portfolios: Sequence[SectorComponentSectorPortfolio],
) -> SectorComponentUiMetadataResponse:
    return SectorComponentUiMetadataResponse(
        ok=True,
        parameterVersion=_config_text(config, "parameter_version", "sector_component_backtest_unknown"),
        modelVersion=_config_text(config, "model_version", "sector_component_backtest_model_unknown"),
        allSectorOption={
            "label": "전체 섹터",
            "value": "ALL",
            "sectorScope": {"mode": "all", "sectorId": None},
        },
        sectorOptions=[
            {
                "label": portfolio.display_name,
                "value": portfolio.sector_id,
                "sectorId": portfolio.sector_id,
                "portfolioId": portfolio.portfolio_id,
                "enabled": portfolio.enabled,
                "assetCount": portfolio.asset_count,
                "assets": [_asset_payload(asset) for asset in portfolio.assets],
                "warnings": _warning_payloads(portfolio.warnings),
                "reasonCodes": _option_reason_codes(portfolio),
            }
            for portfolio in enabled_sector_component_portfolios(portfolios)
        ],
        warnings=[],
        reasonCodes=["SECTOR_COMPONENT_UI_METADATA_BUILT"],
    )


def _asset_payload(asset: Any) -> dict[str, Any]:
    return {
        "assetCode": asset.asset_code,
        "name": asset.name,
        "category": asset.category,
        "weight": asset.weight,
        "role": asset.role,
        "market": asset.market,
        "exchange": asset.exchange,
        "currency": asset.currency,
        "minWeight": asset.min_weight,
        "maxWeight": asset.max_weight,
        "riskTags": list(asset.risk_tags),
    }


def _option_reason_codes(portfolio: SectorComponentSectorPortfolio) -> list[str]:
    values = {"SECTOR_PORTFOLIO_CONFIG_LOADED", *portfolio.reason_codes}
    if portfolio.warnings:
        values.add("REVIEW_REQUIRED")
    return sorted(values)


def _warning_payloads(warnings: Sequence[str]) -> list[dict[str, str]]:
    return [
        {
            "code": warning.split(":", 1)[0],
            "message": warning,
            "fallbackState": "REVIEW_REQUIRED",
        }
        for warning in warnings
    ]


def _config_text(config: Any, field_name: str, default: str) -> str:
    if isinstance(config, Mapping):
        value = config.get(field_name, default)
    else:
        value = getattr(config, field_name, default)
    return value if isinstance(value, str) and value.strip() else default
