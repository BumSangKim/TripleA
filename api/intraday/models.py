from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class IntradayPriceSnapshot:
    symbol: str
    market: str
    captured_at: datetime
    price: Decimal
    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    volume: Decimal | None = None
    value_traded: Decimal | None = None
    change_rate: Decimal | None = None
    source: str = "unknown"
    quality_score: float = 1.0
    is_stale: bool = False
    raw_payload: dict[str, Any] | None = None
    id: int | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class IntradayEvent:
    symbol: str
    market: str
    event_type: str
    event_level: str
    detected_at: datetime
    lookback_minutes: int
    base_price: Decimal | None
    current_price: Decimal
    change_rate: Decimal | None
    volume_ratio: Decimal | None
    reason_code: str
    message: str
    source_snapshot_id: int | None = None
    acknowledged: bool = False
    id: int | None = None
    created_at: str | None = None


@dataclass(frozen=True)
class IntradayAlert:
    event_id: int
    symbol: str
    alert_level: str
    channel: str
    dedupe_key: str
    sent_at: datetime
    status: str
    message: str
    id: int | None = None
    created_at: str | None = None


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
