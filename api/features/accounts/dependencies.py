from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.accounts.repository import AccountsRepository
from api.features.accounts.service import AccountsService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_accounts_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> AccountsRepository:
    return AccountsRepository(conn)


def get_accounts_service(
    repo: AccountsRepository = Depends(get_accounts_repository),
) -> AccountsService:
    return AccountsService(repo)
