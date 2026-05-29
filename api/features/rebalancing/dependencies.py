from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.rebalancing.repository import RebalancingRepository
from api.features.rebalancing.service import RebalancingService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_rebalancing_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> RebalancingRepository:
    return RebalancingRepository(conn)


def get_rebalancing_service(
    repo: RebalancingRepository = Depends(get_rebalancing_repository),
) -> RebalancingService:
    return RebalancingService(repo)
