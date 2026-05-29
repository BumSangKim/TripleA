from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.orders.repository import OrdersRepository
from api.features.orders.service import OrdersService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_orders_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> OrdersRepository:
    return OrdersRepository(conn)


def get_orders_service(
    repo: OrdersRepository = Depends(get_orders_repository),
) -> OrdersService:
    return OrdersService(repo)
