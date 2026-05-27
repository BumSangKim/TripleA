from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    market: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    source: str
    as_of_date: date
    updated_at: datetime


@dataclass(frozen=True)
class CurrentQuote:
    symbol: str
    market: str
    price: Decimal
    currency: str
    quote_time: datetime
    source: str
    as_of_date: date
    updated_at: datetime


@dataclass(frozen=True)
class MacroObservation:
    indicator_key: str
    date: date
    value: Decimal
    unit: str
    source: str
    as_of_date: date
    release_date: date | None
    updated_at: datetime


@dataclass(frozen=True)
class DataQualityCheck:
    dataset_key: str
    source: str
    as_of_date: date
    quality_score: float
    missing_ratio: float
    is_stale: bool
    warnings: list[str]
    fallback_policy: str
    updated_at: datetime


@dataclass(frozen=True)
class IngestionRun:
    run_id: str
    source_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    row_count: int
    error_message: str | None = None


def decimal_from(value: Any) -> Decimal:
    return Decimal(str(value))
