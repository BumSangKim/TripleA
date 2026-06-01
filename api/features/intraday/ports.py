from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, Sequence

from api.features.intraday.models import IntradayEvent, IntradayPriceSnapshot


class IntradaySnapshotReader(Protocol):
    def latest_snapshots(
        self,
        *,
        market: str | None = None,
        symbols: list[str] | None = None,
        limit: int = 100,
    ) -> Sequence[IntradayPriceSnapshot]: ...

    def snapshots_for_symbol(
        self,
        *,
        symbol: str,
        market: str,
        start_at: datetime,
        end_at: datetime,
    ) -> Sequence[IntradayPriceSnapshot]: ...


class IntradayEventReader(Protocol):
    def recent_events(
        self,
        *,
        limit: int = 100,
        symbol: str | None = None,
        event_type: str | None = None,
        event_level: str | None = None,
        acknowledged: bool | None = None,
    ) -> Sequence[IntradayEvent]: ...


class IntradayEventAcknowledger(Protocol):
    def acknowledge_event(self, event_id: int) -> bool: ...


class IntradayCollector(Protocol):
    def collect_once(self, *, config: Any | None = None, force: bool = False) -> Any: ...
