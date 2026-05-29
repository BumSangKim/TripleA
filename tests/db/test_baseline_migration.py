import importlib
import sqlite3

from api.db.migrations.runner import run_migrations

_m = importlib.import_module("api.db.migrations.0001_baseline_existing_schema")
apply = _m.apply
VERSION = _m.VERSION


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_baseline_migration_creates_core_tables():
    conn = make_conn()
    run_migrations(conn, [(VERSION, apply)])

    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for required in ["accounts", "holdings", "order_drafts", "backtest_runs"]:
        assert required in tables, f"Table '{required}' not created by baseline migration"


def test_baseline_migration_is_idempotent():
    conn = make_conn()
    run_migrations(conn, [(VERSION, apply)])
    run_migrations(conn, [(VERSION, apply)])
    row = conn.execute(
        "SELECT COUNT(*) FROM schema_migrations WHERE version=?", (VERSION,)
    ).fetchone()
    assert row[0] == 1
