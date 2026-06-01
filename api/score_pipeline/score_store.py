from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, date, datetime
import json
import sqlite3
from typing import Any

from api.testbed.schema import ensure_testbed_tables


def store_score(
    conn: sqlite3.Connection,
    *,
    snapshot_id: str,
    entity_type: str,
    entity_id: str,
    score_name: str,
    score_value: float,
    confidence: float,
    data_quality: float,
    reason_codes: list[str] | None = None,
) -> None:
    ensure_testbed_tables(conn)
    conn.execute(
        """
        INSERT INTO score_store (snapshot_id, entity_type, entity_id, score_name, score_value, confidence, data_quality, reason_codes_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_id, entity_type, entity_id, score_name) DO UPDATE SET
            score_value=excluded.score_value,
            confidence=excluded.confidence,
            data_quality=excluded.data_quality,
            reason_codes_json=excluded.reason_codes_json
        """,
        (
            snapshot_id,
            entity_type,
            entity_id,
            score_name,
            score_value,
            confidence,
            data_quality,
            json.dumps(reason_codes or [], sort_keys=True),
        ),
    )
    conn.commit()


class SQLiteScoreStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.ensure_tables()

    def ensure_tables(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS score_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                feature_snapshot_id TEXT NOT NULL,
                as_of_date TEXT NOT NULL,
                event_profile TEXT NOT NULL,
                parameter_version TEXT NOT NULL,
                model_version TEXT NOT NULL,
                status TEXT NOT NULL,
                warnings_json TEXT NOT NULL DEFAULT '[]',
                started_at TEXT NOT NULL,
                finished_at TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE TABLE IF NOT EXISTS score_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                score_key TEXT NOT NULL,
                score_type TEXT NOT NULL,
                subject_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                source_plugin_id TEXT NOT NULL,
                source_feature_key TEXT NOT NULL,
                raw_value REAL,
                normalized_score REAL NOT NULL,
                smoothed_score REAL NOT NULL,
                confidence_adjusted_score REAL NOT NULL,
                decision_score REAL NOT NULL,
                previous_score REAL,
                score_change REAL NOT NULL,
                confidence REAL NOT NULL,
                data_quality REAL NOT NULL,
                stability REAL NOT NULL,
                smoothing_method TEXT NOT NULL,
                base_span INTEGER NOT NULL,
                effective_span INTEGER NOT NULL,
                span_override_applied INTEGER NOT NULL,
                span_override_reason TEXT,
                event_profile TEXT NOT NULL,
                override_expires_at TEXT,
                reason_codes_json TEXT NOT NULL DEFAULT '[]',
                warnings_json TEXT NOT NULL DEFAULT '[]',
                as_of_date TEXT NOT NULL,
                feature_snapshot_id TEXT NOT NULL,
                parameter_version TEXT NOT NULL,
                model_version TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_score_values_previous
            ON score_values(score_key, subject_type, subject_id, as_of_date);
            """
        )
        self.conn.commit()

    def create_run(
        self,
        run_id: str,
        feature_snapshot_id: str,
        as_of_date: date,
        event_profile: str,
        parameter_version: str,
        model_version: str,
        status: str,
        warnings: list[str],
    ) -> None:
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """
            INSERT INTO score_runs
            (run_id, feature_snapshot_id, as_of_date, event_profile, parameter_version, model_version, status, warnings_json, started_at, finished_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                feature_snapshot_id,
                as_of_date.isoformat(),
                event_profile,
                parameter_version,
                model_version,
                status,
                json.dumps(warnings),
                now,
                now,
            ),
        )
        self.conn.commit()

    def insert_value(self, run_id: str, output: Any) -> None:
        data = asdict(output)
        self.conn.execute(
            """
            INSERT INTO score_values (
                run_id, score_key, score_type, subject_type, subject_id, source_plugin_id, source_feature_key,
                raw_value, normalized_score, smoothed_score, confidence_adjusted_score, decision_score,
                previous_score, score_change, confidence, data_quality, stability, smoothing_method,
                base_span, effective_span, span_override_applied, span_override_reason, event_profile,
                override_expires_at, reason_codes_json, warnings_json, as_of_date, feature_snapshot_id,
                parameter_version, model_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                output.score_key,
                output.score_type,
                output.subject_type,
                output.subject_id,
                output.source_plugin_id,
                output.source_feature_key,
                output.raw_value,
                output.normalized_score,
                output.smoothed_score,
                output.confidence_adjusted_score,
                output.decision_score,
                output.previous_score,
                output.score_change,
                output.confidence,
                output.data_quality,
                output.stability,
                output.smoothing_method,
                output.base_span,
                output.effective_span,
                int(output.span_override_applied),
                output.span_override_reason,
                output.event_profile,
                output.override_expires_at.isoformat() if output.override_expires_at else None,
                json.dumps(data["reason_codes"]),
                json.dumps(data["warnings"]),
                output.as_of_date.isoformat(),
                output.feature_snapshot_id,
                output.parameter_version,
                output.model_version,
            ),
        )
        self.conn.commit()

    def lookup_previous_score(
        self,
        score_key: str,
        subject_type: str,
        subject_id: str,
        before_date: date,
    ) -> float | None:
        row = self.conn.execute(
            """
            SELECT decision_score
            FROM score_values
            WHERE score_key=? AND subject_type=? AND subject_id=? AND as_of_date < ?
            ORDER BY as_of_date DESC, id DESC
            LIMIT 1
            """,
            (score_key, subject_type, subject_id, before_date.isoformat()),
        ).fetchone()
        return None if row is None else float(row["decision_score"])

    def values_for_run(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT * FROM score_values WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        return [dict(row) for row in rows]
