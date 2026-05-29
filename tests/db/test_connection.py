import sqlite3

import pytest

from api.db.connection import get_conn


def test_get_conn_context_manager():
    with get_conn() as conn:
        assert conn is not None
        result = conn.execute("SELECT 1").fetchone()
        assert result is not None


def test_get_conn_row_factory():
    with get_conn() as conn:
        assert conn.row_factory is sqlite3.Row


def test_get_conn_closes_after_block():
    captured = []
    with get_conn() as conn:
        captured.append(conn)
    # connection is closed; trying to use it should fail
    with pytest.raises(Exception):
        captured[0].execute("SELECT 1")
