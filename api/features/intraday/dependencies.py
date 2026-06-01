from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.intraday import alert, collector, repository
from api.features.intraday.config import load_intraday_config
from api.features.intraday.models import IntradayEvent, IntradayPriceSnapshot
from api.features.intraday.service import IntradayService


def get_intraday_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


class DbIntradaySnapshotReader:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def latest_snapshots(
        self,
        *,
        market: str | None = None,
        symbols: list[str] | None = None,
        limit: int = 100,
    ) -> list[IntradayPriceSnapshot]:
        return repository.latest_snapshots(market=market, symbols=symbols, limit=limit, db_session=self._conn)

    def snapshots_for_symbol(
        self,
        *,
        symbol: str,
        market: str,
        start_at: datetime,
        end_at: datetime,
    ) -> list[IntradayPriceSnapshot]:
        return repository.snapshots_for_symbol(
            symbol=symbol,
            market=market,
            start_at=start_at,
            end_at=end_at,
            db_session=self._conn,
        )


class DbIntradayEventReader:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def recent_events(
        self,
        *,
        limit: int = 100,
        symbol: str | None = None,
        event_type: str | None = None,
        event_level: str | None = None,
        acknowledged: bool | None = None,
    ) -> list[IntradayEvent]:
        return repository.recent_events(
            limit=limit,
            symbol=symbol,
            event_type=event_type,
            event_level=event_level,
            acknowledged=acknowledged,
            db_session=self._conn,
        )


class DbIntradayEventAcknowledger:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def acknowledge_event(self, event_id: int) -> bool:
        return alert.acknowledge_intraday_event(self._conn, event_id)


class DbIntradayCollector:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def collect_once(self, *, config: Any | None = None, force: bool = False) -> Any:
        return collector.collect_intraday_once(
            self._conn,
            config=config or load_intraday_config(),
            force=force,
        )


def get_intraday_service(
    conn: sqlite3.Connection = Depends(get_intraday_db),
) -> IntradayService:
    return IntradayService(
        snapshot_reader=DbIntradaySnapshotReader(conn),
        event_reader=DbIntradayEventReader(conn),
        event_acknowledger=DbIntradayEventAcknowledger(conn),
        collector=DbIntradayCollector(conn),
    )
