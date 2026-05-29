from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.market_data.repository import MarketDataRepository
from api.features.market_data.service import MarketDataService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_market_data_repository(conn: sqlite3.Connection = Depends(get_db)) -> MarketDataRepository:
    return MarketDataRepository(conn)


def get_market_data_service(
    repo: MarketDataRepository = Depends(get_market_data_repository),
) -> MarketDataService:
    return MarketDataService(repo)
