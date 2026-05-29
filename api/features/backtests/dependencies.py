from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.backtests.repository import BacktestsRepository
from api.features.backtests.service import BacktestsService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_backtests_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> BacktestsRepository:
    return BacktestsRepository(conn)


def get_backtests_service(
    repo: BacktestsRepository = Depends(get_backtests_repository),
) -> BacktestsService:
    return BacktestsService(repo)
