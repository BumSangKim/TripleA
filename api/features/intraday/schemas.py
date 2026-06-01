from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from api.features.intraday.models import IntradayEvent, IntradayPriceSnapshot


@dataclass(frozen=True)
class IntradaySnapshotPayload:
    id: int | None
    symbol: str
    market: str
    captured_at: str
    price: float | None
    open_price: float | None
    high_price: float | None
    low_price: float | None
    volume: float | None
    value_traded: float | None
    change_rate: float | None
    source: str
    quality_score: float
    is_stale: bool

    @classmethod
    def from_snapshot(cls, snapshot: IntradayPriceSnapshot) -> "IntradaySnapshotPayload":
        return cls(
            id=snapshot.id,
            symbol=snapshot.symbol,
            market=snapshot.market,
            captured_at=snapshot.captured_at.isoformat(),
            price=_decimal(snapshot.price),
            open_price=_decimal(snapshot.open_price),
            high_price=_decimal(snapshot.high_price),
            low_price=_decimal(snapshot.low_price),
            volume=_decimal(snapshot.volume),
            value_traded=_decimal(snapshot.value_traded),
            change_rate=_decimal(snapshot.change_rate),
            source=snapshot.source,
            quality_score=snapshot.quality_score,
            is_stale=snapshot.is_stale,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "market": self.market,
            "captured_at": self.captured_at,
            "price": self.price,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "volume": self.volume,
            "value_traded": self.value_traded,
            "change_rate": self.change_rate,
            "source": self.source,
            "quality_score": self.quality_score,
            "is_stale": self.is_stale,
        }


@dataclass(frozen=True)
class IntradayEventPayload:
    id: int | None
    symbol: str
    market: str
    event_type: str
    event_level: str
    detected_at: str
    lookback_minutes: int
    base_price: float | None
    current_price: float | None
    change_rate: float | None
    volume_ratio: float | None
    reason_code: str
    message: str
    source_snapshot_id: int | None
    acknowledged: bool

    @classmethod
    def from_event(cls, event: IntradayEvent) -> "IntradayEventPayload":
        return cls(
            id=event.id,
            symbol=event.symbol,
            market=event.market,
            event_type=event.event_type,
            event_level=event.event_level,
            detected_at=event.detected_at.isoformat(),
            lookback_minutes=event.lookback_minutes,
            base_price=_decimal(event.base_price),
            current_price=_decimal(event.current_price),
            change_rate=_decimal(event.change_rate),
            volume_ratio=_decimal(event.volume_ratio),
            reason_code=event.reason_code,
            message=event.message,
            source_snapshot_id=event.source_snapshot_id,
            acknowledged=event.acknowledged,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "market": self.market,
            "event_type": self.event_type,
            "event_level": self.event_level,
            "detected_at": self.detected_at,
            "lookback_minutes": self.lookback_minutes,
            "base_price": self.base_price,
            "current_price": self.current_price,
            "change_rate": self.change_rate,
            "volume_ratio": self.volume_ratio,
            "reason_code": self.reason_code,
            "message": self.message,
            "source_snapshot_id": self.source_snapshot_id,
            "acknowledged": self.acknowledged,
        }


@dataclass(frozen=True)
class IntradayAcknowledgeResult:
    ok: bool
    event_id: int
    reason_code: str | None = None


@dataclass(frozen=True)
class IntradayCollectionPayload:
    started_at: str
    finished_at: str
    requested_symbols: int
    successful_symbols: int
    failed_symbols: int
    inserted_snapshots: int
    status: str
    warnings: list[dict[str, Any]]

    @classmethod
    def from_result(cls, result: Any) -> "IntradayCollectionPayload":
        return cls(
            started_at=str(getattr(result, "started_at")),
            finished_at=str(getattr(result, "finished_at")),
            requested_symbols=int(getattr(result, "requested_symbols")),
            successful_symbols=int(getattr(result, "successful_symbols")),
            failed_symbols=int(getattr(result, "failed_symbols")),
            inserted_snapshots=int(getattr(result, "inserted_snapshots")),
            status=str(getattr(result, "status")),
            warnings=[_warning_dict(warning) for warning in getattr(result, "warnings", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "requested_symbols": self.requested_symbols,
            "successful_symbols": self.successful_symbols,
            "failed_symbols": self.failed_symbols,
            "inserted_snapshots": self.inserted_snapshots,
            "status": self.status,
            "warnings": self.warnings,
        }


def _warning_dict(warning: Any) -> dict[str, Any]:
    if hasattr(warning, "__dict__"):
        return dict(warning.__dict__)
    if isinstance(warning, dict):
        return dict(warning)
    return {"message": str(warning)}


def _decimal(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)
