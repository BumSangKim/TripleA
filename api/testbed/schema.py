from __future__ import annotations

import sqlite3


def ensure_testbed_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS data_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT NOT NULL UNIQUE,
            as_of_date TEXT NOT NULL,
            data_cutoff_at TEXT NOT NULL,
            source_tables_json TEXT NOT NULL,
            quality_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS feature_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            feature_name TEXT NOT NULL,
            feature_value REAL NOT NULL,
            as_of_date TEXT NOT NULL,
            source TEXT,
            quality_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(snapshot_id, entity_type, entity_id, feature_name)
        );

        CREATE TABLE IF NOT EXISTS score_store (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            score_name TEXT NOT NULL,
            score_value REAL NOT NULL,
            confidence REAL NOT NULL,
            data_quality REAL NOT NULL,
            reason_codes_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(snapshot_id, entity_type, entity_id, score_name)
        );

        CREATE TABLE IF NOT EXISTS strategy_decision_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL UNIQUE,
            snapshot_id TEXT,
            as_of_date TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            reason_codes_json TEXT,
            warnings_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS parameter_sets (
            parameter_set_id TEXT PRIMARY KEY,
            parent_parameter_set_id TEXT,
            parameters_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            promoted INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS optimization_runs (
            optimization_run_id TEXT PRIMARY KEY,
            search_method TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            summary_json TEXT
        );

        CREATE TABLE IF NOT EXISTS optimization_candidates (
            candidate_id TEXT PRIMARY KEY,
            optimization_run_id TEXT NOT NULL,
            parameter_set_id TEXT NOT NULL,
            status TEXT NOT NULL,
            metrics_json TEXT,
            failure_reasons_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS decision_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL,
            realized_label TEXT,
            metrics_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    conn.commit()
