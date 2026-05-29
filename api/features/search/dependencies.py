from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.search.repository import SearchRepository
from api.features.search.service import SearchService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_search_repository(conn: sqlite3.Connection = Depends(get_db)) -> SearchRepository:
    return SearchRepository(conn)


def get_search_service(
    repo: SearchRepository = Depends(get_search_repository),
) -> SearchService:
    return SearchService(repo)
