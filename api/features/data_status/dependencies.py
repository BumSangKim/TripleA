from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.data_status.repository import DataStatusRepository
from api.features.data_status.service import DataStatusService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_data_status_repository(conn: sqlite3.Connection = Depends(get_db)) -> DataStatusRepository:
    return DataStatusRepository(conn)


def get_data_status_service(
    repo: DataStatusRepository = Depends(get_data_status_repository),
) -> DataStatusService:
    return DataStatusService(repo)
