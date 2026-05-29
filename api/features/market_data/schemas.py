from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class AssetUniverseSchema(BaseModel):
    assetCode: str
    symbol: str
    name: Optional[str]
    assetClass: str
    market: Optional[str]
    currency: str
    sourceType: str
    isActive: bool


class AssetCoverageSchema(BaseModel):
    assetCode: str
    currency: str
    priceStartDate: Optional[str]
    priceEndDate: Optional[str]
    pricePoints: int
    ok: bool
    message: Optional[str] = None


class FxCoverageSchema(BaseModel):
    baseCurrency: str
    quoteCurrency: str
    rateStartDate: Optional[str]
    rateEndDate: Optional[str]
    ratePoints: int
    ok: bool
    message: Optional[str] = None


class MarketDataCoverageResponse(BaseModel):
    ok: bool
    assets: List[AssetCoverageSchema]
    fxRates: List[FxCoverageSchema]
    missingMessages: List[str]
