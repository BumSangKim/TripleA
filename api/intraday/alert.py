from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from api.intraday.config import IntradayMonitoringConfig, load_intraday_config
from api.intraday.models import IntradayAlert, IntradayEvent, ensure_aware
from api.intraday.repository import (
    IntradayRepositoryError,
    find_duplicate_alert,
    insert_alert,
    insert_event,
    mark_event_acknowledged,
)


@dataclass(frozen=True)
class AlertPayload:
    symbol: str
    market: str
    event_type: str
    event_level: str
    lookback_minutes: int
    change_rate: Decimal | None
    volume_ratio: Decimal | None
    message: str
    reason_code: str
    detected_at: str
    dedupe_key: str
    event_id: int


@dataclass(frozen=True)
class AlertEngineWarning:
    symbol: str | None
    reason_code: str
    message: str


@dataclass(frozen=True)
class AlertProcessResult:
    persisted_events: int = 0
    generated_alerts: int = 0
    suppressed_alerts: int = 0
    payloads: list[AlertPayload] = field(default_factory=list)
    warnings: list[AlertEngineWarning] = field(default_factory=list)


def process_intraday_events(
    db_session: sqlite3.Connection,
    events: list[IntradayEvent],
    config: IntradayMonitoringConfig | None = None,
    *,
    channel: str = "internal",
) -> AlertProcessResult:
    config = config or load_intraday_config()
    persisted = 0
    generated = 0
    suppressed = 0
    payloads: list[AlertPayload] = []
    warnings: list[AlertEngineWarning] = []
    for event in events:
        try:
            saved = insert_event(event, db_session)
            persisted += 1
            dedupe_key = build_dedupe_key(saved)
            since = ensure_aware(saved.detected_at) - timedelta(minutes=config.duplicate_suppression_minutes)
            if find_duplicate_alert(dedupe_key=dedupe_key, since=since, db_session=db_session):
                suppressed += 1
                continue
            payload = build_alert_payload(saved, dedupe_key)
            insert_alert(
                IntradayAlert(
                    event_id=saved.id,
                    symbol=saved.symbol,
                    alert_level=saved.event_level,
                    channel=channel,
                    dedupe_key=dedupe_key,
                    sent_at=saved.detected_at,
                    status="READY",
                    message=saved.message,
                ),
                db_session,
            )
            generated += 1
            payloads.append(payload)
        except IntradayRepositoryError as exc:
            warnings.append(
                AlertEngineWarning(
                    symbol=event.symbol,
                    reason_code="INTRADAY_ALERT_REPOSITORY_ERROR",
                    message=str(exc),
                )
            )
    return AlertProcessResult(
        persisted_events=persisted,
        generated_alerts=generated,
        suppressed_alerts=suppressed,
        payloads=payloads,
        warnings=warnings,
    )


def acknowledge_intraday_event(db_session: sqlite3.Connection, event_id: int) -> bool:
    return mark_event_acknowledged(event_id, db_session)


def build_dedupe_key(event: IntradayEvent) -> str:
    return f"{event.symbol}:{event.event_type}:{event.event_level}:{event.lookback_minutes}"


def build_alert_payload(event: IntradayEvent, dedupe_key: str | None = None) -> AlertPayload:
    if event.id is None:
        raise ValueError("event must be persisted before building an alert payload")
    return AlertPayload(
        symbol=event.symbol,
        market=event.market,
        event_type=event.event_type,
        event_level=event.event_level,
        lookback_minutes=event.lookback_minutes,
        change_rate=event.change_rate,
        volume_ratio=event.volume_ratio,
        message=event.message,
        reason_code=event.reason_code,
        detected_at=ensure_aware(event.detected_at).isoformat(),
        dedupe_key=dedupe_key or build_dedupe_key(event),
        event_id=event.id,
    )
