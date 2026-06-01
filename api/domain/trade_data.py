from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TradeSeriesItem:
    period: str
    country: str | None
    flow: str
    item_code: str
    item_name: str | None
    amount_usd: float | None
    quantity: float | None
    unit: str | None
    yoy: float | None
    mom: float | None
    source: str | None
    release_date: date


@dataclass(frozen=True)
class TradeSnapshot:
    as_of_date: date
    lookback_months: int
    items: list[TradeSeriesItem]
