from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Mapping, Sequence

from api.data.capex_jobs import CapexFetchJobRequest, CapexFetchJobResult, CapexFetchStatus
from api.data.capex_models import RawCompanyMetricPoint, RawTimeSeriesPoint, SourceFetchLogRecord
from api.data.capex_ports import CapexCompanyMetricSourceClient, CapexRawDataRepository, CapexTimeSeriesSourceClient


RouteKind = Literal["time_series", "company_metrics"]


@dataclass(frozen=True)
class CapexIngestionRoute:
    source_id: str
    kind: RouteKind
    client: CapexTimeSeriesSourceClient | CapexCompanyMetricSourceClient
    company_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if self.kind not in {"time_series", "company_metrics"}:
            raise ValueError("kind must be time_series or company_metrics")
        object.__setattr__(self, "company_ids", tuple(self.company_ids))


@dataclass
class CapexIngestionService:
    repository: CapexRawDataRepository
    routes: Mapping[str, CapexIngestionRoute] = field(default_factory=dict)

    def run_fetch_job(self, request: CapexFetchJobRequest) -> CapexFetchJobResult:
        started_at = datetime.now(tz=UTC)
        route = self.routes.get(request.source_id)
        if route is None:
            return self._result(
                request,
                status=CapexFetchStatus.FAILED,
                started_at=started_at,
                rows_fetched=0,
                rows_stored=0,
                warnings=("REVIEW_REQUIRED",),
                errors=(f"missing ingestion route for source_id: {request.source_id}",),
            )

        fetched_time_series: list[RawTimeSeriesPoint] = []
        fetched_company_metrics: list[RawCompanyMetricPoint] = []
        warnings: list[str] = []
        errors: list[str] = []
        for metric_id in request.metric_ids:
            try:
                if route.kind == "time_series":
                    fetched_time_series.extend(
                        route.client.fetch_time_series(
                            metric_id=metric_id,
                            start=request.start_date,
                            end=request.end_date,
                            as_of=request.as_of,
                        )
                    )
                else:
                    if not route.company_ids:
                        raise ValueError("company_ids are required for company metric ingestion")
                    fetched_company_metrics.extend(
                        route.client.fetch_company_metrics(
                            company_ids=route.company_ids,
                            metric_ids=(metric_id,),
                            start_period=request.start_date.isoformat(),
                            end_period=request.end_date.isoformat(),
                            as_of=request.as_of,
                        )
                    )
            except Exception as exc:
                warnings.append(f"FETCH_FAILED:{metric_id}")
                errors.append(f"{metric_id}: {exc}")

        rows_fetched = len(fetched_time_series) + len(fetched_company_metrics)
        rows_stored = 0
        if rows_fetched and not request.dry_run:
            if fetched_time_series:
                rows_stored += self.repository.upsert_time_series(fetched_time_series)
            if fetched_company_metrics:
                rows_stored += self.repository.upsert_company_metrics(fetched_company_metrics)

        status = _status(rows_fetched=rows_fetched, errors=errors, requested_count=len(request.metric_ids))
        if request.dry_run and rows_fetched:
            warnings.append("DRY_RUN_NO_PERSIST")
        result = self._result(
            request,
            status=status,
            started_at=started_at,
            rows_fetched=rows_fetched,
            rows_stored=rows_stored,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )
        if not request.dry_run:
            self.repository.record_fetch_log(
                SourceFetchLogRecord(
                    fetch_id=request.request_id or f"{request.source_id}:{started_at.isoformat()}",
                    source_id=request.source_id,
                    started_at=started_at,
                    finished_at=result.finished_at,
                    status=result.status.value,
                    row_count=rows_stored,
                    metric_ids=list(request.metric_ids),
                    reason_codes=[result.status.value],
                    warnings=list(result.warnings),
                )
            )
        return result

    def _result(
        self,
        request: CapexFetchJobRequest,
        *,
        status: CapexFetchStatus,
        started_at: datetime,
        rows_fetched: int,
        rows_stored: int,
        warnings: Sequence[str],
        errors: Sequence[str],
    ) -> CapexFetchJobResult:
        return CapexFetchJobResult(
            request_id=request.request_id,
            source_id=request.source_id,
            metric_ids=request.metric_ids,
            status=status,
            dry_run=request.dry_run,
            requested_at=request.requested_at,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            rows_fetched=rows_fetched,
            rows_stored=rows_stored,
            warnings=tuple(warnings),
            errors=tuple(errors),
        )


def _status(*, rows_fetched: int, errors: Sequence[str], requested_count: int) -> CapexFetchStatus:
    if rows_fetched and errors:
        return CapexFetchStatus.PARTIAL_SUCCESS
    if rows_fetched:
        return CapexFetchStatus.SUCCESS
    if errors and len(errors) >= requested_count:
        return CapexFetchStatus.FAILED
    if errors:
        return CapexFetchStatus.PARTIAL_SUCCESS
    return CapexFetchStatus.SKIPPED
