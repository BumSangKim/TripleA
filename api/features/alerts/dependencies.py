from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.alerts.repository import AlertsRepository
from api.features.alerts.service import AlertsService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_alerts_repository(conn: sqlite3.Connection = Depends(get_db)) -> AlertsRepository:
    return AlertsRepository(conn)


def get_alerts_service(
    repo: AlertsRepository = Depends(get_alerts_repository),
) -> AlertsService:
    return AlertsService(repo)
