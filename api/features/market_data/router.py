from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from api.features.market_data.dependencies import get_market_data_service
from api.features.market_data.schemas import (
    AssetCoverageSchema,
    AssetUniverseSchema,
    FxCoverageSchema,
    MarketDataCoverageResponse,
)
from api.features.market_data.service import MarketDataService

router = APIRouter(tags=["market-data"])


@router.get("/api/market-data/assets", response_model=List[AssetUniverseSchema])
def market_data_assets(
    active_only: bool = True,
    svc: MarketDataService = Depends(get_market_data_service),
):
    items = svc.list_assets(active_only=active_only)
    return [
        AssetUniverseSchema(
            assetCode=item.asset_code,
            symbol=item.symbol,
            name=item.name,
            assetClass=item.asset_class,
            market=item.market,
            currency=item.currency,
            sourceType=item.source_type,
            isActive=item.is_active,
        )
        for item in items
    ]


@router.get("/api/market-data/coverage", response_model=MarketDataCoverageResponse)
def market_data_coverage(
    start_date: str,
    end_date: str,
    svc: MarketDataService = Depends(get_market_data_service),
):
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"날짜 형식 오류: {e}") from e
    if start > end:
        raise HTTPException(status_code=422, detail="start_date는 end_date보다 앞이어야 합니다.")
    coverage = svc.get_coverage(start, end)
    return MarketDataCoverageResponse(
        ok=coverage.ok,
        assets=[
            AssetCoverageSchema(
                assetCode=a.asset_code,
                currency=a.currency,
                priceStartDate=a.price_start_date.isoformat() if a.price_start_date else None,
                priceEndDate=a.price_end_date.isoformat() if a.price_end_date else None,
                pricePoints=a.price_points,
                ok=a.ok,
                message=a.message,
            )
            for a in coverage.assets
        ],
        fxRates=[
            FxCoverageSchema(
                baseCurrency=f.base_currency,
                quoteCurrency=f.quote_currency,
                rateStartDate=f.rate_start_date.isoformat() if f.rate_start_date else None,
                rateEndDate=f.rate_end_date.isoformat() if f.rate_end_date else None,
                ratePoints=f.rate_points,
                ok=f.ok,
                message=f.message,
            )
            for f in coverage.fx_rates
        ],
        missingMessages=list(coverage.missing_messages),
    )
