from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from api.data.capex_ingestion_service import CapexIngestionRoute, CapexIngestionService
from api.data.capex_jobs import CapexFetchJobRequest, CapexFetchStatus
from api.data.capex_models import RawCompanyMetricPoint, RawTimeSeriesPoint
from api.data.capex_repository import SqliteCapexRawDataRepository


NOW = datetime(2024, 5, 31, 9, tzinfo=UTC)


class FakeTimeSeriesClient:
    client_name = "fake_time_series"
    source_id = "ECOS"

    def __init__(self, failures: set[str] | None = None):
        self.failures = failures or set()
        self.calls: list[str] = []

    def list_metrics(self) -> tuple[str, ...]:
        return ("macro.fx.usdkrw", "macro.rate.level")

    def fetch_time_series(
        self,
        *,
        metric_id: str,
        start: date,
        end: date,
        as_of: datetime | None = None,
    ) -> tuple[RawTimeSeriesPoint, ...]:
        self.calls.append(metric_id)
        if metric_id in self.failures:
            raise RuntimeError("fixture source failure")
        return (
            RawTimeSeriesPoint(
                source="ECOS",
                source_id="731Y001:0000001",
                metric_id=metric_id,
                observation_date=start,
                value=Decimal("1375.5"),
                unit="KRW_per_USD",
                available_at=NOW,
                updated_at=NOW,
            ),
        )


class FakeCompanyMetricClient:
    client_name = "fake_company"
    source_id = "SEC_EDGAR_COMPANYFACTS"

    def list_metrics(self) -> tuple[str, ...]:
        return ("capital_expenditures_usd",)

    def fetch_company_metrics(
        self,
        *,
        company_ids: tuple[str, ...],
        metric_ids: tuple[str, ...],
        start_period: str | None = None,
        end_period: str | None = None,
        as_of: datetime | None = None,
    ) -> tuple[RawCompanyMetricPoint, ...]:
        return (
            RawCompanyMetricPoint(
                source="SEC_EDGAR_COMPANYFACTS",
                source_id="sec_companyfacts",
                company_id=company_ids[0],
                metric_id=metric_ids[0],
                period="CY2024Q1",
                value=Decimal("260"),
                unit="USD",
                available_at=NOW,
                updated_at=NOW,
            ),
        )


def make_repo() -> SqliteCapexRawDataRepository:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return SqliteCapexRawDataRepository(conn)


def request(*, dry_run: bool, metric_ids: tuple[str, ...] = ("macro.fx.usdkrw",)) -> CapexFetchJobRequest:
    return CapexFetchJobRequest(
        request_id="req-1",
        source_id="ECOS",
        metric_ids=metric_ids,
        start_date=date(2024, 5, 1),
        end_date=date(2024, 5, 1),
        requested_at=NOW,
        dry_run=dry_run,
        as_of=NOW,
    )


def service(repo: SqliteCapexRawDataRepository, client: FakeTimeSeriesClient) -> CapexIngestionService:
    return CapexIngestionService(
        repository=repo,
        routes={
            "ECOS": CapexIngestionRoute(source_id="ECOS", kind="time_series", client=client),
        },
    )


def test_dry_run_fetches_but_does_not_persist() -> None:
    repo = make_repo()
    client = FakeTimeSeriesClient()

    result = service(repo, client).run_fetch_job(request(dry_run=True))

    assert client.calls == ["macro.fx.usdkrw"]
    assert result.status is CapexFetchStatus.SUCCESS
    assert result.rows_fetched == 1
    assert result.rows_stored == 0
    assert "DRY_RUN_NO_PERSIST" in result.warnings
    assert repo.read_time_series(metric_id="macro.fx.usdkrw") == ()
    assert repo.list_fetch_logs() == ()


def test_normal_run_persists_idempotently() -> None:
    repo = make_repo()
    ingestion = service(repo, FakeTimeSeriesClient())

    first = ingestion.run_fetch_job(request(dry_run=False))
    second = ingestion.run_fetch_job(request(dry_run=False))

    assert first.status is CapexFetchStatus.SUCCESS
    assert second.status is CapexFetchStatus.SUCCESS
    assert len(repo.read_time_series(metric_id="macro.fx.usdkrw")) == 1
    assert repo.list_fetch_logs(source_id="ECOS")[0].status == "SUCCESS"


def test_partial_source_failure_returns_partial_success_with_warnings() -> None:
    repo = make_repo()
    ingestion = service(repo, FakeTimeSeriesClient(failures={"macro.rate.level"}))

    result = ingestion.run_fetch_job(request(dry_run=False, metric_ids=("macro.fx.usdkrw", "macro.rate.level")))

    assert result.status is CapexFetchStatus.PARTIAL_SUCCESS
    assert result.rows_fetched == 1
    assert result.rows_stored == 1
    assert result.warnings == ("FETCH_FAILED:macro.rate.level",)
    assert result.errors and "macro.rate.level" in result.errors[0]
    assert len(repo.read_time_series(metric_id="macro.fx.usdkrw")) == 1


def test_company_metric_route_persists_company_rows() -> None:
    repo = make_repo()
    ingestion = CapexIngestionService(
        repository=repo,
        routes={
            "SEC_EDGAR_COMPANYFACTS": CapexIngestionRoute(
                source_id="SEC_EDGAR_COMPANYFACTS",
                kind="company_metrics",
                client=FakeCompanyMetricClient(),
                company_ids=("sample_ai",),
            )
        },
    )
    job = CapexFetchJobRequest(
        request_id="req-company",
        source_id="SEC_EDGAR_COMPANYFACTS",
        metric_ids=("capital_expenditures_usd",),
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        requested_at=NOW,
        dry_run=False,
        as_of=NOW,
    )

    result = ingestion.run_fetch_job(job)

    assert result.status is CapexFetchStatus.SUCCESS
    rows = repo.read_company_metrics(company_id="sample_ai", metric_id="capital_expenditures_usd")
    assert len(rows) == 1
    assert rows[0].value == Decimal("260")


def test_missing_route_is_conservative_failure() -> None:
    repo = make_repo()
    ingestion = CapexIngestionService(repository=repo, routes={})

    result = ingestion.run_fetch_job(request(dry_run=False))

    assert result.status is CapexFetchStatus.FAILED
    assert result.warnings == ("REVIEW_REQUIRED",)
    assert result.rows_stored == 0


def test_ingestion_service_has_no_scheduler_network_or_execution_surface() -> None:
    source = Path("api/data/capex_ingestion_service.py").read_text()
    forbidden_terms = (
        "asyncio",
        "threading",
        "apscheduler",
        "celery",
        "requests",
        "httpx",
        "api.brokers",
        "api.features.orders",
        "api.strategy",
        "submit_order",
        "place_order",
    )

    assert not any(term in source for term in forbidden_terms)
