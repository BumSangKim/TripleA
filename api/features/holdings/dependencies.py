from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.holdings.repository import HoldingsRepository
from api.features.holdings.service import HoldingsService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_holdings_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> HoldingsRepository:
    return HoldingsRepository(conn)


def get_holdings_service(
    repo: HoldingsRepository = Depends(get_holdings_repository),
) -> HoldingsService:
    return HoldingsService(repo)
