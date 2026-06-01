from __future__ import annotations

from datetime import datetime
from typing import Any

from api.features.intraday.ports import (
    IntradayCollector,
    IntradayEventAcknowledger,
    IntradayEventReader,
    IntradaySnapshotReader,
)
from api.features.intraday.schemas import (
    IntradayAcknowledgeResult,
    IntradayCollectionPayload,
    IntradayEventPayload,
    IntradaySnapshotPayload,
)


class IntradayService:
    def __init__(
        self,
        *,
        snapshot_reader: IntradaySnapshotReader,
        event_reader: IntradayEventReader,
        event_acknowledger: IntradayEventAcknowledger,
        collector: IntradayCollector,
    ) -> None:
        self._snapshot_reader = snapshot_reader
        self._event_reader = event_reader
        self._event_acknowledger = event_acknowledger
        self._collector = collector

    def latest_snapshots(
        self,
        *,
        market: str | None = None,
        symbols: list[str] | None = None,
        limit: int = 100,
    ) -> list[IntradaySnapshotPayload]:
        snapshots = self._snapshot_reader.latest_snapshots(market=market, symbols=symbols, limit=limit)
        return [IntradaySnapshotPayload.from_snapshot(snapshot) for snapshot in snapshots]

    def snapshots_for_symbol(
        self,
        *,
        symbol: str,
        market: str,
        start_at: datetime,
        end_at: datetime,
        limit: int = 100,
    ) -> list[IntradaySnapshotPayload]:
        snapshots = self._snapshot_reader.snapshots_for_symbol(
            symbol=symbol,
            market=market,
            start_at=start_at,
            end_at=end_at,
        )
        return [IntradaySnapshotPayload.from_snapshot(snapshot) for snapshot in snapshots][-limit:]

    def recent_events(
        self,
        *,
        event_type: str | None = None,
        event_level: str | None = None,
        acknowledged: bool | None = None,
        limit: int = 100,
    ) -> list[IntradayEventPayload]:
        events = self._event_reader.recent_events(
            event_type=event_type,
            event_level=event_level,
            acknowledged=acknowledged,
            limit=limit,
        )
        return [IntradayEventPayload.from_event(event) for event in events]

    def symbol_events(self, *, symbol: str, limit: int = 100) -> list[IntradayEventPayload]:
        events = self._event_reader.recent_events(symbol=symbol, limit=limit)
        return [IntradayEventPayload.from_event(event) for event in events]

    def acknowledge_event(self, event_id: int) -> IntradayAcknowledgeResult:
        updated = self._event_acknowledger.acknowledge_event(event_id)
        if not updated:
            return IntradayAcknowledgeResult(ok=False, event_id=event_id, reason_code="INTRADAY_EVENT_NOT_FOUND")
        return IntradayAcknowledgeResult(ok=True, event_id=event_id)

    def collect_once(self, *, config: Any | None = None, force: bool = False) -> IntradayCollectionPayload:
        return IntradayCollectionPayload.from_result(self._collector.collect_once(config=config, force=force))
