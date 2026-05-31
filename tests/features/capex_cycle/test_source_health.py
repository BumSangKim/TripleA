from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from api.data.capex_models import DataQualityIssueRecord, SourceFetchLogRecord
from api.features.capex_cycle.source_health import CapexSourceHealthStatus, compute_capex_source_health


AS_OF = date(2026, 5, 31)


class FakeRepository:
    def __init__(self, logs=(), issues=()):
        self.logs = tuple(logs)
        self.issues = tuple(issues)
        self.fetch_called = False

    def list_fetch_logs(self, *, source_id=None, limit=100):
        return self.logs

    def list_quality_issues(self, *, metric_id=None, source_id=None, as_of_date=None, limit=100):
        return self.issues

    def run_fetch_job(self, request):
        self.fetch_called = True
        raise AssertionError("source health must not trigger fetch")


def fetch_log(source_id: str, *, status: str = "SUCCESS", days_old: int = 1) -> SourceFetchLogRecord:
    at = datetime(2026, 5, 31 - days_old, tzinfo=UTC)
    return SourceFetchLogRecord(
        fetch_id=f"{source_id}-{status}-{days_old}",
        source_id=source_id,
        started_at=at,
        finished_at=at,
        status=status,
        row_count=3,
        metric_ids=["macro.fx.usdkrw"],
        reason_codes=["FETCH_OK"],
        warnings=[],
    )


def quality_issue(source_id: str) -> DataQualityIssueRecord:
    at = datetime(2026, 5, 30, tzinfo=UTC)
    return DataQualityIssueRecord(
        issue_id=f"{source_id}-issue",
        source_id=source_id,
        metric_id="macro.fx.usdkrw",
        severity="ERROR",
        reason_code="BAD_SOURCE_ROW",
        message="fixture issue",
        as_of_date=AS_OF,
        available_at=at,
        updated_at=at,
    )


def find(items, source_id: str):
    return next(item for item in items if item.source_id == source_id)


def test_ok_source_status() -> None:
    repo = FakeRepository(logs=[fetch_log("ECOS", days_old=1)])

    items = compute_capex_source_health(repo, as_of_date=AS_OF)

    ecos = find(items, "ECOS")
    assert ecos.status == CapexSourceHealthStatus.OK
    assert ecos.quality_score == 1.0
    assert repo.fetch_called is False


def test_stale_source_status_blocks_risk_increase() -> None:
    repo = FakeRepository(logs=[fetch_log("ECOS", days_old=20)])

    items = compute_capex_source_health(repo, as_of_date=AS_OF)

    ecos = find(items, "ECOS")
    assert ecos.status == CapexSourceHealthStatus.STALE
    assert any(warning.code == "SOURCE_HEALTH_RISK_INCREASE_BLOCKED" for warning in ecos.warnings)


def test_partial_status_from_quality_issue() -> None:
    repo = FakeRepository(logs=[fetch_log("ECOS", days_old=1)], issues=[quality_issue("ECOS")])

    items = compute_capex_source_health(repo, as_of_date=AS_OF)

    ecos = find(items, "ECOS")
    assert ecos.status == CapexSourceHealthStatus.PARTIAL
    assert ecos.quality_score < 1.0


def test_disabled_optional_vendor_status() -> None:
    items = compute_capex_source_health(FakeRepository(), as_of_date=AS_OF)

    vendor = find(items, "LICENSED_VENDOR_PLACEHOLDER")
    assert vendor.status == CapexSourceHealthStatus.DISABLED
    assert any(warning.code == "SOURCE_HEALTH_RISK_INCREASE_BLOCKED" for warning in vendor.warnings)


def test_fixture_only_status_for_unmatched_fixture_log() -> None:
    repo = FakeRepository(logs=[fetch_log("capex_fixture", days_old=1)])

    items = compute_capex_source_health(repo, as_of_date=AS_OF)

    fixture = find(items, "capex_fixture")
    assert fixture.status == CapexSourceHealthStatus.FIXTURE_ONLY
    assert fixture.quality_score == 0.5


def test_source_health_has_no_network_or_execution_surface() -> None:
    source = Path("api/features/capex_cycle/source_health.py").read_text()
    forbidden = (
        "requests",
        "httpx",
        "api.brokers",
        "api.features.orders",
        "api.strategy",
        "submit_order",
        "place_order",
    )

    assert not any(term in source for term in forbidden)
