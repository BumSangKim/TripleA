from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from api.plugin_boundary.contracts import FeatureValue, PluginSignal


def ensure_traceability_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS plugin_boundary_feature_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feature_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            feature_value_json TEXT,
            unit TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            available_at TEXT NOT NULL,
            source_dataset_ids_json TEXT NOT NULL,
            source_plugin_ids_json TEXT NOT NULL,
            calculation_method TEXT NOT NULL,
            feature_version TEXT NOT NULL,
            parameter_version TEXT,
            data_quality REAL NOT NULL,
            missing_ratio REAL NOT NULL,
            is_stale INTEGER NOT NULL,
            warnings_json TEXT,
            reason_codes_json TEXT,
            metadata_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_plugin_boundary_feature_available
        ON plugin_boundary_feature_values(feature_id, entity_type, entity_id, available_at);

        CREATE TABLE IF NOT EXISTS plugin_boundary_plugin_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id TEXT NOT NULL,
            plugin_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            source TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            signal_value_json TEXT,
            signal_unit TEXT NOT NULL,
            signal_direction TEXT,
            source_native INTEGER NOT NULL,
            calculation_method TEXT NOT NULL,
            plugin_version TEXT,
            signal_version TEXT NOT NULL,
            as_of_date TEXT NOT NULL,
            available_at TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            quality_score REAL NOT NULL,
            source_dataset_ids_json TEXT NOT NULL,
            reason_codes_json TEXT,
            warnings_json TEXT,
            metadata_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_plugin_boundary_signal_available
        ON plugin_boundary_plugin_signals(signal_id, entity_type, entity_id, available_at);
        """
    )
    conn.commit()


def save_feature_value(conn: sqlite3.Connection, feature: FeatureValue) -> int:
    ensure_traceability_tables(conn)
    cursor = conn.execute(
        """
        INSERT INTO plugin_boundary_feature_values (
            feature_id, entity_type, entity_id, feature_value_json, unit, as_of_date, available_at,
            source_dataset_ids_json, source_plugin_ids_json, calculation_method, feature_version,
            parameter_version, data_quality, missing_ratio, is_stale, warnings_json,
            reason_codes_json, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            feature.feature_id,
            feature.entity_type,
            feature.entity_id,
            json.dumps(feature.feature_value, sort_keys=True),
            feature.unit,
            feature.as_of_date.isoformat(),
            feature.available_at.isoformat(),
            json.dumps(feature.source_dataset_ids, sort_keys=True),
            json.dumps(feature.source_plugin_ids, sort_keys=True),
            feature.calculation_method,
            feature.feature_version,
            feature.parameter_version,
            feature.data_quality,
            feature.missing_ratio,
            1 if feature.is_stale else 0,
            json.dumps(feature.warnings, sort_keys=True),
            json.dumps(feature.reason_codes, sort_keys=True),
            json.dumps(feature.metadata, sort_keys=True),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def read_feature_values(
    conn: sqlite3.Connection,
    *,
    feature_id: str,
    entity_type: str,
    entity_id: str,
    decision_time: datetime | None = None,
) -> list[FeatureValue]:
    ensure_traceability_tables(conn)
    where = "feature_id=? AND entity_type=? AND entity_id=?"
    params: list[Any] = [feature_id, entity_type, entity_id]
    if decision_time is not None:
        where += " AND available_at<=?"
        params.append(decision_time.isoformat())
    rows = conn.execute(
        f"""
        SELECT *
        FROM plugin_boundary_feature_values
        WHERE {where}
        ORDER BY available_at DESC, id DESC
        """,
        params,
    ).fetchall()
    return [_feature_from_row(row) for row in rows]


def save_plugin_signal(conn: sqlite3.Connection, signal: PluginSignal) -> int:
    ensure_traceability_tables(conn)
    cursor = conn.execute(
        """
        INSERT INTO plugin_boundary_plugin_signals (
            signal_id, plugin_id, provider, source, entity_type, entity_id, signal_value_json,
            signal_unit, signal_direction, source_native, calculation_method, plugin_version,
            signal_version, as_of_date, available_at, retrieved_at, quality_score,
            source_dataset_ids_json, reason_codes_json, warnings_json, metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal.signal_id,
            signal.plugin_id,
            signal.provider,
            signal.source,
            signal.entity_type,
            signal.entity_id,
            json.dumps(signal.signal_value, sort_keys=True),
            signal.signal_unit,
            signal.signal_direction,
            1 if signal.source_native else 0,
            signal.calculation_method,
            signal.plugin_version,
            signal.signal_version,
            signal.as_of_date.isoformat(),
            signal.available_at.isoformat(),
            signal.retrieved_at.isoformat(),
            signal.quality_score,
            json.dumps(signal.source_dataset_ids, sort_keys=True),
            json.dumps(signal.reason_codes, sort_keys=True),
            json.dumps(signal.warnings, sort_keys=True),
            json.dumps(signal.metadata, sort_keys=True),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def read_plugin_signals(
    conn: sqlite3.Connection,
    *,
    signal_id: str,
    entity_type: str,
    entity_id: str | None,
    decision_time: datetime | None = None,
) -> list[PluginSignal]:
    ensure_traceability_tables(conn)
    where = "signal_id=? AND entity_type=? AND entity_id IS ?"
    params: list[Any] = [signal_id, entity_type, entity_id]
    if decision_time is not None:
        where += " AND available_at<=?"
        params.append(decision_time.isoformat())
    rows = conn.execute(
        f"""
        SELECT *
        FROM plugin_boundary_plugin_signals
        WHERE {where}
        ORDER BY available_at DESC, id DESC
        """,
        params,
    ).fetchall()
    return [_signal_from_row(row) for row in rows]


def _feature_from_row(row: sqlite3.Row | tuple[Any, ...]) -> FeatureValue:
    data = dict(row)
    return FeatureValue(
        feature_id=data["feature_id"],
        entity_type=data["entity_type"],
        entity_id=data["entity_id"],
        feature_value=json.loads(data["feature_value_json"]),
        unit=data["unit"],
        as_of_date=datetime.fromisoformat(data["as_of_date"]).date(),
        available_at=datetime.fromisoformat(data["available_at"]),
        source_dataset_ids=json.loads(data["source_dataset_ids_json"]),
        source_plugin_ids=json.loads(data["source_plugin_ids_json"]),
        calculation_method=data["calculation_method"],
        feature_version=data["feature_version"],
        parameter_version=data["parameter_version"],
        data_quality=float(data["data_quality"]),
        missing_ratio=float(data["missing_ratio"]),
        is_stale=bool(data["is_stale"]),
        warnings=json.loads(data["warnings_json"] or "[]"),
        reason_codes=json.loads(data["reason_codes_json"] or "[]"),
        metadata=json.loads(data["metadata_json"] or "{}"),
    )


def _signal_from_row(row: sqlite3.Row | tuple[Any, ...]) -> PluginSignal:
    data = dict(row)
    return PluginSignal(
        signal_id=data["signal_id"],
        plugin_id=data["plugin_id"],
        provider=data["provider"],
        source=data["source"],
        entity_type=data["entity_type"],
        entity_id=data["entity_id"],
        signal_value=json.loads(data["signal_value_json"]),
        signal_unit=data["signal_unit"],
        signal_direction=data["signal_direction"],
        source_native=bool(data["source_native"]),
        calculation_method=data["calculation_method"],
        plugin_version=data["plugin_version"],
        signal_version=data["signal_version"],
        as_of_date=datetime.fromisoformat(data["as_of_date"]).date(),
        available_at=datetime.fromisoformat(data["available_at"]),
        retrieved_at=datetime.fromisoformat(data["retrieved_at"]),
        quality_score=float(data["quality_score"]),
        source_dataset_ids=json.loads(data["source_dataset_ids_json"]),
        reason_codes=json.loads(data["reason_codes_json"] or "[]"),
        warnings=json.loads(data["warnings_json"] or "[]"),
        metadata=json.loads(data["metadata_json"] or "{}"),
    )
