"""0002: raw CapEx data persistence schema."""
from __future__ import annotations

import sqlite3

VERSION = "0002_capex_raw_data_schema"

_SQL = """
    CREATE TABLE IF NOT EXISTS raw_time_series_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        metric_id TEXT NOT NULL,
        observation_date TEXT NOT NULL,
        value TEXT NOT NULL,
        unit TEXT NOT NULL,
        available_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        revision_id TEXT NOT NULL DEFAULT '',
        source_priority INTEGER NOT NULL DEFAULT 0,
        confidence REAL NOT NULL DEFAULT 1.0,
        license_class TEXT NOT NULL DEFAULT 'public',
        attributes_json TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(source, source_id, metric_id, observation_date, revision_id)
    );

    CREATE INDEX IF NOT EXISTS idx_raw_time_series_available_at
    ON raw_time_series_points(available_at);

    CREATE INDEX IF NOT EXISTS idx_raw_time_series_source_metric_date
    ON raw_time_series_points(source, metric_id, observation_date);

    CREATE INDEX IF NOT EXISTS idx_raw_time_series_metric_available
    ON raw_time_series_points(metric_id, available_at);

    CREATE TABLE IF NOT EXISTS raw_company_metric_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        source_id TEXT NOT NULL,
        company_id TEXT NOT NULL,
        metric_id TEXT NOT NULL,
        period TEXT NOT NULL,
        value TEXT NOT NULL,
        unit TEXT NOT NULL,
        available_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        revision_id TEXT NOT NULL DEFAULT '',
        source_priority INTEGER NOT NULL DEFAULT 0,
        confidence REAL NOT NULL DEFAULT 1.0,
        license_class TEXT NOT NULL DEFAULT 'public',
        attributes_json TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')),
        UNIQUE(source, source_id, company_id, metric_id, period, revision_id)
    );

    CREATE INDEX IF NOT EXISTS idx_raw_company_metrics_available_at
    ON raw_company_metric_points(available_at);

    CREATE INDEX IF NOT EXISTS idx_raw_company_metrics_source_metric_period
    ON raw_company_metric_points(source, metric_id, period);

    CREATE INDEX IF NOT EXISTS idx_raw_company_metrics_company_metric_available
    ON raw_company_metric_points(company_id, metric_id, available_at);

    CREATE TABLE IF NOT EXISTS source_fetch_logs (
        fetch_id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL,
        row_count INTEGER NOT NULL DEFAULT 0,
        metric_ids_json TEXT,
        reason_codes_json TEXT,
        warnings_json TEXT,
        license_class TEXT NOT NULL DEFAULT 'public',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE INDEX IF NOT EXISTS idx_source_fetch_logs_source_started
    ON source_fetch_logs(source_id, started_at);

    CREATE INDEX IF NOT EXISTS idx_source_fetch_logs_status
    ON source_fetch_logs(status);

    CREATE TABLE IF NOT EXISTS data_quality_issues (
        issue_id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        metric_id TEXT NOT NULL,
        severity TEXT NOT NULL,
        reason_code TEXT NOT NULL,
        message TEXT NOT NULL,
        as_of_date TEXT NOT NULL,
        available_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        fallback_state TEXT NOT NULL DEFAULT 'REVIEW_REQUIRED',
        confidence REAL NOT NULL DEFAULT 0.0,
        license_class TEXT NOT NULL DEFAULT 'public',
        created_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE INDEX IF NOT EXISTS idx_data_quality_issues_as_of_date
    ON data_quality_issues(as_of_date);

    CREATE INDEX IF NOT EXISTS idx_data_quality_issues_available_at
    ON data_quality_issues(available_at);

    CREATE INDEX IF NOT EXISTS idx_data_quality_issues_source_metric
    ON data_quality_issues(source_id, metric_id);
"""


def apply(conn: sqlite3.Connection) -> None:
    conn.executescript(_SQL)
    conn.commit()
