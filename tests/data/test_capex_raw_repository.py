from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from api.data.capex_models import (
    DataQualityIssueRecord,
    RawCompanyMetricPoint,
    RawTimeSeriesPoint,
    SourceFetchLogRecord,
)
from api.data.capex_repository import SqliteCapexRawDataRepository


def make_repo() -> SqliteCapexRawDataRepository:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return SqliteCapexRawDataRepository(conn)


def ts_point(
    observed: date,
    *,
    available_at: datetime,
    value: str = "1.0",
    revision_id: str | None = None,
) -> RawTimeSeriesPoint:
    return RawTimeSeriesPoint(
        source="ECOS",
        source_id="731Y001:0000001",
        metric_id="macro.fx.usdkrw",
        observation_date=observed,
        value=Decimal(value),
        unit="KRW_per_USD",
        available_at=available_at,
        updated_at=available_at,
        revision_id=revision_id,
        attributes={"fixture": True},
    )


def cm_point(period: str, *, available_at: datetime, value: str = "10") -> RawCompanyMetricPoint:
    return RawCompanyMetricPoint(
        source="SEC_EDGAR_COMPANYFACTS",
        source_id="sec_companyfacts",
        company_id="sample_ai",
        metric_id="capital_expenditures_usd",
        period=period,
        value=Decimal(value),
        unit="USD",
        available_at=available_at,
        updated_at=available_at,
        revision_id="rev-1",
    )


def test_time_series_upsert_is_idempotent() -> None:
    repo = make_repo()
    point = ts_point(date(2024, 5, 1), available_at=datetime(2024, 5, 2, tzinfo=UTC))

    assert repo.upsert_time_series([point]) == 1
    assert repo.upsert_time_series([point]) == 1

    rows = repo.read_time_series(metric_id="macro.fx.usdkrw", source_id="731Y001:0000001")
    assert len(rows) == 1
    assert rows[0].value == Decimal("1.0")
    assert rows[0].attributes == {"fixture": True}


def test_time_series_read_by_metric_source_and_date_range() -> None:
    repo = make_repo()
    repo.upsert_time_series(
        [
            ts_point(date(2024, 5, 1), available_at=datetime(2024, 5, 2, tzinfo=UTC), value="1375.5"),
            ts_point(date(2024, 5, 2), available_at=datetime(2024, 5, 3, tzinfo=UTC), value="1379.2"),
        ]
    )

    rows = repo.read_time_series(
        metric_id="macro.fx.usdkrw",
        source_id="731Y001:0000001",
        start=date(2024, 5, 2),
        end=date(2024, 5, 2),
    )

    assert [row.observation_date for row in rows] == [date(2024, 5, 2)]
    assert rows[0].value == Decimal("1379.2")


def test_time_series_pit_query_uses_available_at() -> None:
    repo = make_repo()
    repo.upsert_time_series(
        [
            ts_point(date(2024, 5, 1), available_at=datetime(2024, 5, 2, tzinfo=UTC), value="1"),
            ts_point(date(2024, 5, 2), available_at=datetime(2024, 5, 4, tzinfo=UTC), value="2"),
        ]
    )

    rows = repo.read_time_series(
        metric_id="macro.fx.usdkrw",
        as_of=datetime(2024, 5, 3, tzinfo=UTC),
    )

    assert [row.observation_date for row in rows] == [date(2024, 5, 1)]


def test_company_metric_upsert_read_and_pit_filter() -> None:
    repo = make_repo()
    repo.upsert_company_metrics(
        [
            cm_point("CY2024Q1", available_at=datetime(2024, 5, 10, tzinfo=UTC), value="260"),
            cm_point("CY2024Q2", available_at=datetime(2024, 8, 10, tzinfo=UTC), value="300"),
        ]
    )
    repo.upsert_company_metrics([cm_point("CY2024Q1", available_at=datetime(2024, 5, 10, tzinfo=UTC), value="260")])

    rows = repo.read_company_metrics(
        company_id="sample_ai",
        metric_id="capital_expenditures_usd",
        as_of=datetime(2024, 6, 1, tzinfo=UTC),
    )

    assert len(rows) == 1
    assert rows[0].period == "CY2024Q1"
    assert rows[0].value == Decimal("260")


def test_fetch_logs_and_quality_issues_persist() -> None:
    repo = make_repo()
    started_at = datetime(2024, 5, 1, tzinfo=UTC)
    repo.record_fetch_log(
        SourceFetchLogRecord(
            fetch_id="fetch-1",
            source_id="ECOS",
            started_at=started_at,
            finished_at=started_at,
            status="SUCCESS",
            row_count=2,
            metric_ids=["macro.fx.usdkrw"],
            reason_codes=["FETCH_OK"],
            warnings=[],
        )
    )
    repo.record_quality_issue(
        DataQualityIssueRecord(
            issue_id="issue-1",
            source_id="ECOS",
            metric_id="macro.fx.usdkrw",
            severity="WARNING",
            reason_code="STALE_DATA",
            message="fixture stale warning",
            as_of_date=date(2024, 5, 1),
            available_at=started_at,
            updated_at=started_at,
        )
    )

    assert repo.list_fetch_logs(source_id="ECOS")[0].metric_ids == ["macro.fx.usdkrw"]
    issue = repo.list_quality_issues(metric_id="macro.fx.usdkrw")[0]
    assert issue.fallback_state == "REVIEW_REQUIRED"
    assert issue.reason_code == "STALE_DATA"


def test_repository_does_not_create_local_db_artifacts() -> None:
    local_db_artifacts = [
        path
        for pattern in ("*.db", "*.sqlite", "*.sqlite3")
        for path in Path(".").glob(pattern)
        if path.is_file()
    ]

    assert local_db_artifacts == []
