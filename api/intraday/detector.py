from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from api.intraday.config import IntradayMonitoringConfig, load_intraday_config
from api.intraday.models import IntradayEvent, IntradayPriceSnapshot
from api.intraday.repository import lookback_base_snapshot


@dataclass(frozen=True)
class DetectionWarning:
    symbol: str
    reason_code: str
    message: str
    lookback_minutes: int | None = None


@dataclass(frozen=True)
class DetectionResult:
    events: list[IntradayEvent] = field(default_factory=list)
    warnings: list[DetectionWarning] = field(default_factory=list)


def detect_events_for_snapshot(
    db_session: sqlite3.Connection,
    current: IntradayPriceSnapshot,
    config: IntradayMonitoringConfig | None = None,
) -> DetectionResult:
    config = config or load_intraday_config()
    if current.is_stale or current.quality_score < 0.8:
        return DetectionResult(
            warnings=[
                DetectionWarning(
                    symbol=current.symbol,
                    reason_code="INTRADAY_LOW_DATA_QUALITY",
                    message="current snapshot quality is too low for normal event detection",
                )
            ]
        )
    events: list[IntradayEvent] = []
    warnings: list[DetectionWarning] = []
    for window in config.lookback_windows_minutes:
        base = lookback_base_snapshot(
            symbol=current.symbol,
            market=current.market,
            target_at=current.captured_at - timedelta(minutes=window),
            db_session=db_session,
        )
        if base is None:
            warnings.append(
                DetectionWarning(
                    symbol=current.symbol,
                    reason_code="INTRADAY_INSUFFICIENT_LOOKBACK_DATA",
                    message=f"missing base snapshot for {window}-minute lookback",
                    lookback_minutes=window,
                )
            )
            continue
        if base.price <= 0:
            warnings.append(
                DetectionWarning(
                    symbol=current.symbol,
                    reason_code="INTRADAY_INVALID_BASE_PRICE",
                    message=f"invalid base price for {window}-minute lookback",
                    lookback_minutes=window,
                )
            )
            continue
        change_rate = ((current.price - base.price) / base.price) * Decimal("100")
        volume_ratio = _volume_ratio(current, base)
        price_event_type, price_level = _price_event(change_rate, config)
        volume_level = _level_for_positive(volume_ratio, config.volume_spike_thresholds) if volume_ratio is not None else None

        if price_event_type is not None and price_level is not None:
            events.append(
                _event(
                    current=current,
                    base=base,
                    event_type=price_event_type,
                    event_level=price_level,
                    lookback_minutes=window,
                    change_rate=change_rate,
                    volume_ratio=volume_ratio,
                    reason_code="INTRADAY_SURGE_PRICE_CHANGE" if price_event_type == "SURGE" else "INTRADAY_DROP_PRICE_CHANGE",
                )
            )
        if volume_level is not None:
            events.append(
                _event(
                    current=current,
                    base=base,
                    event_type="VOLUME_SPIKE",
                    event_level=volume_level,
                    lookback_minutes=window,
                    change_rate=change_rate,
                    volume_ratio=volume_ratio,
                    reason_code="INTRADAY_VOLUME_SPIKE",
                )
            )
        if price_event_type == "SURGE" and price_level is not None and volume_level is not None:
            events.append(
                _event(
                    current=current,
                    base=base,
                    event_type="SURGE_WITH_VOLUME",
                    event_level=_max_level(price_level, volume_level),
                    lookback_minutes=window,
                    change_rate=change_rate,
                    volume_ratio=volume_ratio,
                    reason_code="INTRADAY_SURGE_WITH_VOLUME",
                )
            )
        if price_event_type == "DROP" and price_level is not None and volume_level is not None:
            events.append(
                _event(
                    current=current,
                    base=base,
                    event_type="DROP_WITH_VOLUME",
                    event_level=_max_level(price_level, volume_level),
                    lookback_minutes=window,
                    change_rate=change_rate,
                    volume_ratio=volume_ratio,
                    reason_code="INTRADAY_DROP_WITH_VOLUME",
                )
            )
    return DetectionResult(events=events, warnings=warnings)


def _price_event(change_rate: Decimal, config: IntradayMonitoringConfig) -> tuple[str | None, str | None]:
    surge = _level_for_positive(change_rate, config.surge_thresholds)
    if surge is not None:
        return "SURGE", surge
    drop = _level_for_negative(change_rate, config.drop_thresholds)
    if drop is not None:
        return "DROP", drop
    return None, None


def _level_for_positive(value: Decimal | None, thresholds: dict[str, float] | None) -> str | None:
    if value is None or thresholds is None:
        return None
    if value >= Decimal(str(thresholds.get("critical", "Infinity"))):
        return "CRITICAL"
    if value >= Decimal(str(thresholds.get("warning", "Infinity"))):
        return "WARNING"
    if value >= Decimal(str(thresholds.get("watch", "Infinity"))):
        return "WATCH"
    return None


def _level_for_negative(value: Decimal, thresholds: dict[str, float] | None) -> str | None:
    if thresholds is None:
        return None
    if value <= Decimal(str(thresholds.get("critical", "-Infinity"))):
        return "CRITICAL"
    if value <= Decimal(str(thresholds.get("warning", "-Infinity"))):
        return "WARNING"
    if value <= Decimal(str(thresholds.get("watch", "-Infinity"))):
        return "WATCH"
    return None


def _volume_ratio(current: IntradayPriceSnapshot, base: IntradayPriceSnapshot) -> Decimal | None:
    if current.volume is None or base.volume is None or base.volume <= 0:
        return None
    return current.volume / base.volume


def _event(
    *,
    current: IntradayPriceSnapshot,
    base: IntradayPriceSnapshot,
    event_type: str,
    event_level: str,
    lookback_minutes: int,
    change_rate: Decimal,
    volume_ratio: Decimal | None,
    reason_code: str,
) -> IntradayEvent:
    return IntradayEvent(
        symbol=current.symbol,
        market=current.market,
        event_type=event_type,
        event_level=event_level,
        detected_at=current.captured_at,
        lookback_minutes=lookback_minutes,
        base_price=base.price,
        current_price=current.price,
        change_rate=change_rate,
        volume_ratio=volume_ratio,
        reason_code=reason_code,
        message=f"{current.symbol} {event_type} {event_level} over {lookback_minutes}m",
        source_snapshot_id=current.id,
    )


def _max_level(first: str, second: str) -> str:
    priority = {"INFO": 0, "WATCH": 1, "WARNING": 2, "CRITICAL": 3}
    return first if priority[first] >= priority[second] else second
