from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.macro.repository import MacroRepository
from api.features.macro.service import MacroService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_macro_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> MacroRepository:
    return MacroRepository(conn)


def get_macro_service(
    repo: MacroRepository = Depends(get_macro_repository),
) -> MacroService:
    return MacroService(repo)
