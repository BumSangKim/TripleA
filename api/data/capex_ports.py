from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, Sequence, runtime_checkable

from api.data.capex_models import (
    DataQualityIssueRecord,
    RawCompanyMetricPoint,
    RawTimeSeriesPoint,
    SourceFetchLogRecord,
)


@runtime_checkable
class CapexRawDataRepository(Protocol):
    def upsert_time_series(self, points: Sequence[RawTimeSeriesPoint]) -> int:
        ...

    def upsert_company_metrics(self, points: Sequence[RawCompanyMetricPoint]) -> int:
        ...

    def record_fetch_log(self, record: SourceFetchLogRecord) -> None:
        ...

    def record_quality_issue(self, record: DataQualityIssueRecord) -> None:
        ...

    def read_time_series(
        self,
        *,
        metric_id: str,
        source_id: str | None = None,
        start: date | None = None,
        end: date | None = None,
        as_of: datetime | None = None,
    ) -> Sequence[RawTimeSeriesPoint]:
        ...

    def read_company_metrics(
        self,
        *,
        company_id: str,
        metric_id: str,
        source_id: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        as_of: datetime | None = None,
    ) -> Sequence[RawCompanyMetricPoint]:
        ...

    def list_fetch_logs(self, *, source_id: str | None = None, limit: int = 100) -> Sequence[SourceFetchLogRecord]:
        ...

    def list_quality_issues(
        self,
        *,
        metric_id: str | None = None,
        source_id: str | None = None,
        as_of_date: date | None = None,
        limit: int = 100,
    ) -> Sequence[DataQualityIssueRecord]:
        ...


@runtime_checkable
class CapexTimeSeriesSourceClient(Protocol):
    client_name: str
    source_id: str

    def list_metrics(self) -> Sequence[str]:
        ...

    def fetch_time_series(
        self,
        *,
        metric_id: str,
        start: date,
        end: date,
        as_of: datetime | None = None,
    ) -> Sequence[RawTimeSeriesPoint]:
        ...


@runtime_checkable
class CapexCompanyMetricSourceClient(Protocol):
    client_name: str
    source_id: str

    def list_metrics(self) -> Sequence[str]:
        ...

    def fetch_company_metrics(
        self,
        *,
        company_ids: Sequence[str],
        metric_ids: Sequence[str],
        start_period: str | None = None,
        end_period: str | None = None,
        as_of: datetime | None = None,
    ) -> Sequence[RawCompanyMetricPoint]:
        ...
