from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class AssetUniverseData:
    asset_code: str
    symbol: str
    name: Optional[str]
    asset_class: str
    market: Optional[str]
    currency: str
    source_type: str
    is_active: bool


@dataclass(frozen=True)
class AssetCoverageData:
    asset_code: str
    currency: str
    price_start_date: Optional[date]
    price_end_date: Optional[date]
    price_points: int
    ok: bool
    message: Optional[str] = None


@dataclass(frozen=True)
class FxCoverageData:
    base_currency: str
    quote_currency: str
    rate_start_date: Optional[date]
    rate_end_date: Optional[date]
    rate_points: int
    ok: bool
    message: Optional[str] = None


@dataclass(frozen=True)
class MarketDataCoverageData:
    ok: bool
    assets: tuple
    fx_rates: tuple
    missing_messages: tuple
