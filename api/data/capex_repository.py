from __future__ import annotations

import importlib
import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Sequence

from api.data.capex_models import (
    DataQualityIssueRecord,
    RawCompanyMetricPoint,
    RawTimeSeriesPoint,
    SourceFetchLogRecord,
)


def ensure_capex_raw_tables(conn: sqlite3.Connection) -> None:
    migration = importlib.import_module("api.db.migrations.0002_capex_raw_data_schema")
    migration.apply(conn)


class SqliteCapexRawDataRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        ensure_capex_raw_tables(self.conn)

    def upsert_time_series(self, points: Sequence[RawTimeSeriesPoint]) -> int:
        self.conn.executemany(
            """
            INSERT INTO raw_time_series_points (
                source, source_id, metric_id, observation_date, value, unit,
                available_at, updated_at, revision_id, source_priority, confidence,
                license_class, attributes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, source_id, metric_id, observation_date, revision_id) DO UPDATE SET
                value=excluded.value,
                unit=excluded.unit,
                available_at=excluded.available_at,
                updated_at=excluded.updated_at,
                source_priority=excluded.source_priority,
                confidence=excluded.confidence,
                license_class=excluded.license_class,
                attributes_json=excluded.attributes_json
            """,
            [_time_series_values(point) for point in points],
        )
        self.conn.commit()
        return len(points)

    def upsert_company_metrics(self, points: Sequence[RawCompanyMetricPoint]) -> int:
        self.conn.executemany(
            """
            INSERT INTO raw_company_metric_points (
                source, source_id, company_id, metric_id, period, value, unit,
                available_at, updated_at, revision_id, source_priority, confidence,
                license_class, attributes_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, source_id, company_id, metric_id, period, revision_id) DO UPDATE SET
                value=excluded.value,
                unit=excluded.unit,
                available_at=excluded.available_at,
                updated_at=excluded.updated_at,
                source_priority=excluded.source_priority,
                confidence=excluded.confidence,
                license_class=excluded.license_class,
                attributes_json=excluded.attributes_json
            """,
            [_company_metric_values(point) for point in points],
        )
        self.conn.commit()
        return len(points)

    def record_fetch_log(self, record: SourceFetchLogRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO source_fetch_logs (
                fetch_id, source_id, started_at, finished_at, status, row_count,
                metric_ids_json, reason_codes_json, warnings_json, license_class
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fetch_id) DO UPDATE SET
                source_id=excluded.source_id,
                started_at=excluded.started_at,
                finished_at=excluded.finished_at,
                status=excluded.status,
                row_count=excluded.row_count,
                metric_ids_json=excluded.metric_ids_json,
                reason_codes_json=excluded.reason_codes_json,
                warnings_json=excluded.warnings_json,
                license_class=excluded.license_class
            """,
            (
                record.fetch_id,
                record.source_id,
                record.started_at.isoformat(),
                record.finished_at.isoformat() if record.finished_at else None,
                record.status,
                int(record.row_count),
                _json(record.metric_ids),
                _json(record.reason_codes),
                _json(record.warnings),
                record.license_class,
            ),
        )
        self.conn.commit()

    def record_quality_issue(self, record: DataQualityIssueRecord) -> None:
        self.conn.execute(
            """
            INSERT INTO data_quality_issues (
                issue_id, source_id, metric_id, severity, reason_code, message,
                as_of_date, available_at, updated_at, fallback_state, confidence, license_class
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(issue_id) DO UPDATE SET
                source_id=excluded.source_id,
                metric_id=excluded.metric_id,
                severity=excluded.severity,
                reason_code=excluded.reason_code,
                message=excluded.message,
                as_of_date=excluded.as_of_date,
                available_at=excluded.available_at,
                updated_at=excluded.updated_at,
                fallback_state=excluded.fallback_state,
                confidence=excluded.confidence,
                license_class=excluded.license_class
            """,
            (
                record.issue_id,
                record.source_id,
                record.metric_id,
                record.severity,
                record.reason_code,
                record.message,
                record.as_of_date.isoformat(),
                record.available_at.isoformat(),
                record.updated_at.isoformat(),
                record.fallback_state,
                float(record.confidence),
                record.license_class,
            ),
        )
        self.conn.commit()

    def read_time_series(
        self,
        *,
        metric_id: str,
        source_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
        as_of: datetime | None = None,
    ) -> tuple[RawTimeSeriesPoint, ...]:
        where = ["metric_id = ?"]
        params: list[Any] = [metric_id]
        if source_id is not None:
            where.append("source_id = ?")
            params.append(source_id)
        if start is not None:
            where.append("observation_date >= ?")
            params.append(start.isoformat())
        if end is not None:
            where.append("observation_date <= ?")
            params.append(end.isoformat())
        if as_of is not None:
            where.append("available_at <= ?")
            params.append(as_of.isoformat())
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM raw_time_series_points
            WHERE {' AND '.join(where)}
            ORDER BY observation_date, available_at, source_priority
            """,
            params,
        ).fetchall()
        return tuple(_time_series_from_row(row) for row in rows)

    def read_company_metrics(
        self,
        *,
        company_id: str,
        metric_id: str,
        source_id: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        as_of: datetime | None = None,
    ) -> tuple[RawCompanyMetricPoint, ...]:
        where = ["company_id = ?", "metric_id = ?"]
        params: list[Any] = [company_id, metric_id]
        if source_id is not None:
            where.append("source_id = ?")
            params.append(source_id)
        if period_start is not None:
            where.append("period >= ?")
            params.append(period_start)
        if period_end is not None:
            where.append("period <= ?")
            params.append(period_end)
        if as_of is not None:
            where.append("available_at <= ?")
            params.append(as_of.isoformat())
        rows = self.conn.execute(
            f"""
            SELECT *
            FROM raw_company_metric_points
            WHERE {' AND '.join(where)}
            ORDER BY period, available_at, source_priority
            """,
            params,
        ).fetchall()
        return tuple(_company_metric_from_row(row) for row in rows)

    def list_fetch_logs(self, *, source_id: str | None = None, limit: int = 100) -> tuple[SourceFetchLogRecord, ...]:
        if source_id is None:
            rows = self.conn.execute(
                "SELECT * FROM source_fetch_logs ORDER BY started_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM source_fetch_logs WHERE source_id=? ORDER BY started_at DESC LIMIT ?",
                (source_id, int(limit)),
            ).fetchall()
        return tuple(_fetch_log_from_row(row) for row in rows)

    def list_quality_issues(
        self,
        *,
        metric_id: str | None = None,
        source_id: str | None = None,
        as_of_date: date | None = None,
        limit: int = 100,
    ) -> tuple[DataQualityIssueRecord, ...]:
        where: list[str] = []
        params: list[Any] = []
        if metric_id is not None:
            where.append("metric_id = ?")
            params.append(metric_id)
        if source_id is not None:
            where.append("source_id = ?")
            params.append(source_id)
        if as_of_date is not None:
            where.append("as_of_date = ?")
            params.append(as_of_date.isoformat())
        sql = "SELECT * FROM data_quality_issues"
        if where:
            sql += f" WHERE {' AND '.join(where)}"
        sql += " ORDER BY available_at DESC LIMIT ?"
        params.append(int(limit))
        return tuple(_quality_issue_from_row(row) for row in self.conn.execute(sql, params).fetchall())


def _time_series_values(point: RawTimeSeriesPoint) -> tuple[Any, ...]:
    return (
        point.source,
        point.source_id,
        point.metric_id,
        point.observation_date.isoformat(),
        str(point.value),
        point.unit,
        point.available_at.isoformat(),
        point.updated_at.isoformat(),
        point.revision_id or "",
        int(point.source_priority),
        float(point.confidence),
        point.license_class,
        _json(point.attributes),
    )


def _company_metric_values(point: RawCompanyMetricPoint) -> tuple[Any, ...]:
    return (
        point.source,
        point.source_id,
        point.company_id,
        point.metric_id,
        point.period,
        str(point.value),
        point.unit,
        point.available_at.isoformat(),
        point.updated_at.isoformat(),
        point.revision_id or "",
        int(point.source_priority),
        float(point.confidence),
        point.license_class,
        _json(point.attributes),
    )


def _time_series_from_row(row: sqlite3.Row) -> RawTimeSeriesPoint:
    return RawTimeSeriesPoint(
        source=row["source"],
        source_id=row["source_id"],
        metric_id=row["metric_id"],
        observation_date=date.fromisoformat(row["observation_date"]),
        value=Decimal(str(row["value"])),
        unit=row["unit"],
        available_at=datetime.fromisoformat(row["available_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        revision_id=row["revision_id"] or None,
        source_priority=int(row["source_priority"]),
        confidence=float(row["confidence"]),
        license_class=row["license_class"],
        attributes=_dict_json(row["attributes_json"]),
    )


def _company_metric_from_row(row: sqlite3.Row) -> RawCompanyMetricPoint:
    return RawCompanyMetricPoint(
        source=row["source"],
        source_id=row["source_id"],
        company_id=row["company_id"],
        metric_id=row["metric_id"],
        period=row["period"],
        value=Decimal(str(row["value"])),
        unit=row["unit"],
        available_at=datetime.fromisoformat(row["available_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        revision_id=row["revision_id"] or None,
        source_priority=int(row["source_priority"]),
        confidence=float(row["confidence"]),
        license_class=row["license_class"],
        attributes=_dict_json(row["attributes_json"]),
    )


def _fetch_log_from_row(row: sqlite3.Row) -> SourceFetchLogRecord:
    return SourceFetchLogRecord(
        fetch_id=row["fetch_id"],
        source_id=row["source_id"],
        started_at=datetime.fromisoformat(row["started_at"]),
        finished_at=datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None,
        status=row["status"],
        row_count=int(row["row_count"]),
        metric_ids=list(_list_json(row["metric_ids_json"])),
        reason_codes=list(_list_json(row["reason_codes_json"])),
        warnings=list(_list_json(row["warnings_json"])),
        license_class=row["license_class"],
    )


def _quality_issue_from_row(row: sqlite3.Row) -> DataQualityIssueRecord:
    return DataQualityIssueRecord(
        issue_id=row["issue_id"],
        source_id=row["source_id"],
        metric_id=row["metric_id"],
        severity=row["severity"],
        reason_code=row["reason_code"],
        message=row["message"],
        as_of_date=date.fromisoformat(row["as_of_date"]),
        available_at=datetime.fromisoformat(row["available_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        fallback_state=row["fallback_state"],
        confidence=float(row["confidence"]),
        license_class=row["license_class"],
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _dict_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(value)
    return dict(loaded) if isinstance(loaded, dict) else {}


def _list_json(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        return ()
    return tuple(str(item) for item in loaded)
