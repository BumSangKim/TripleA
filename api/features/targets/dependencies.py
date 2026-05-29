from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.targets.repository import TargetsRepository
from api.features.targets.service import TargetsService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_targets_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> TargetsRepository:
    return TargetsRepository(conn)


def get_targets_service(
    repo: TargetsRepository = Depends(get_targets_repository),
) -> TargetsService:
    return TargetsService(repo)
