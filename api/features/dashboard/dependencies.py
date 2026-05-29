from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.dashboard.repository import DashboardRepository
from api.features.dashboard.service import DashboardService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_dashboard_repository(conn: sqlite3.Connection = Depends(get_db)) -> DashboardRepository:
    return DashboardRepository(conn)


def get_dashboard_service(
    repo: DashboardRepository = Depends(get_dashboard_repository),
) -> DashboardService:
    return DashboardService(repo)
