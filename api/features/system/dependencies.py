from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.system.repository import SystemRepository
from api.features.system.service import SystemService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_system_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> SystemRepository:
    return SystemRepository(conn)


def get_system_service(
    repo: SystemRepository = Depends(get_system_repository),
) -> SystemService:
    return SystemService(repo)
