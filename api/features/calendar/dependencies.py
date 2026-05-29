from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.calendar.repository import CalendarRepository
from api.features.calendar.service import CalendarService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_calendar_repository(conn: sqlite3.Connection = Depends(get_db)) -> CalendarRepository:
    return CalendarRepository(conn)


def get_calendar_service(
    repo: CalendarRepository = Depends(get_calendar_repository),
) -> CalendarService:
    return CalendarService(repo)
