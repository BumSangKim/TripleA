from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

from api.db.migrations.runner import run_migrations

_m = importlib.import_module("api.db.migrations.0002_capex_raw_data_schema")
apply = _m.apply
VERSION = _m.VERSION


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    assert row is not None, f"missing table {table_name}"
    return row["sql"]


def index_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
        if row["name"]
    }


def test_raw_capex_migration_creates_required_tables() -> None:
    conn = make_conn()
    run_migrations(conn, [(VERSION, apply)])

    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }

    assert "raw_time_series_points" in tables
    assert "raw_company_metric_points" in tables
    assert "source_fetch_logs" in tables
    assert "data_quality_issues" in tables
    assert "orders" not in tables
    assert "fills" not in tables


def test_raw_capex_migration_includes_pit_fields_and_uniqueness() -> None:
    conn = make_conn()
    run_migrations(conn, [(VERSION, apply)])

    time_series_sql = table_sql(conn, "raw_time_series_points")
    company_metric_sql = table_sql(conn, "raw_company_metric_points")
    quality_sql = table_sql(conn, "data_quality_issues")

    for required in ("available_at", "updated_at", "revision_id"):
        assert required in time_series_sql
        assert required in company_metric_sql
    assert "UNIQUE(source, source_id, metric_id, observation_date, revision_id)" in time_series_sql
    assert "UNIQUE(source, source_id, company_id, metric_id, period, revision_id)" in company_metric_sql
    assert "as_of_date" in quality_sql
    assert "fallback_state" in quality_sql


def test_raw_capex_migration_includes_required_indexes() -> None:
    conn = make_conn()
    run_migrations(conn, [(VERSION, apply)])

    names = index_names(conn)

    assert "idx_raw_time_series_available_at" in names
    assert "idx_raw_time_series_source_metric_date" in names
    assert "idx_raw_company_metrics_available_at" in names
    assert "idx_raw_company_metrics_source_metric_period" in names
    assert "idx_data_quality_issues_as_of_date" in names
    assert "idx_data_quality_issues_source_metric" in names


def test_raw_capex_migration_is_idempotent() -> None:
    conn = make_conn()
    run_migrations(conn, [(VERSION, apply)])
    run_migrations(conn, [(VERSION, apply)])

    row = conn.execute(
        "SELECT COUNT(*) AS count FROM schema_migrations WHERE version=?",
        (VERSION,),
    ).fetchone()

    assert row["count"] == 1


def test_raw_capex_migration_does_not_create_local_database_artifacts() -> None:
    local_db_artifacts = [
        path
        for pattern in ("*.db", "*.sqlite", "*.sqlite3")
        for path in Path(".").glob(pattern)
        if path.is_file()
    ]

    assert local_db_artifacts == []
