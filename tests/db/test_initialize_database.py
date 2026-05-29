import importlib
import os
import sqlite3
import tempfile

from api.db.initialize import initialize_database


def test_initialize_database_creates_tables(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)

    initialize_database()

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for required in ["accounts", "holdings", "order_drafts", "backtest_runs"]:
        assert required in tables


def test_initialize_database_adds_asset_class_column(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)

    initialize_database()

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(holdings)")}
    assert "asset_class" in columns


def test_initialize_database_idempotent(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)

    initialize_database()
    initialize_database()  # second call must not fail
