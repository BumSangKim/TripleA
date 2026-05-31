from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from api.data.capex_jobs import (
    CapexFetchJobContractError,
    CapexFetchJobRequest,
    CapexFetchJobResult,
    CapexFetchStatus,
)


NOW = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)


def test_fetch_job_request_defaults_to_dry_run() -> None:
    request = CapexFetchJobRequest(
        source_id="test_vendor",
        metric_ids=("ai_gpu_backlog", "fab_utilization"),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        requested_at=NOW,
    )

    assert request.dry_run is True
    assert request.metric_ids == ("ai_gpu_backlog", "fab_utilization")


def test_fetch_job_request_serializes_and_round_trips() -> None:
    request = CapexFetchJobRequest(
        request_id="req-1",
        source_id="test_vendor",
        metric_ids=("bio_cdmo_capacity",),
        start_date=date(2025, 1, 1),
        end_date=date(2025, 3, 31),
        requested_at=NOW,
        as_of=NOW,
        metadata={"reason": "manual_smoke"},
    )

    payload = request.to_dict()
    assert payload["start_date"] == "2025-01-01"
    assert payload["requested_at"] == NOW.isoformat()
    assert payload["metric_ids"] == ["bio_cdmo_capacity"]

    assert CapexFetchJobRequest.from_dict(payload) == request


def test_fetch_job_result_serializes_warnings_and_errors() -> None:
    result = CapexFetchJobResult(
        request_id="req-2",
        source_id="test_vendor",
        metric_ids=("ai_datacenter_power",),
        status=CapexFetchStatus.PARTIAL_SUCCESS,
        dry_run=True,
        requested_at=NOW,
        started_at=NOW,
        finished_at=NOW,
        rows_fetched=5,
        rows_stored=0,
        warnings=("missing_optional_metric",),
        errors=("one_metric_failed",),
    )

    payload = result.to_dict()

    assert payload["status"] == "PARTIAL_SUCCESS"
    assert payload["warnings"] == ["missing_optional_metric"]
    assert payload["errors"] == ["one_metric_failed"]
    assert CapexFetchJobResult.from_dict(payload) == result


def test_fetch_job_result_accepts_status_string() -> None:
    result = CapexFetchJobResult(
        request_id=None,
        source_id="test_vendor",
        metric_ids=("ai_capex",),
        status="SKIPPED",
        dry_run=True,
        requested_at=NOW,
        started_at=None,
        finished_at=None,
    )

    assert result.status is CapexFetchStatus.SKIPPED


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"metric_ids": ()}, "metric_ids"),
        ({"start_date": date(2025, 2, 1), "end_date": date(2025, 1, 1)}, "start_date"),
    ],
)
def test_fetch_job_request_rejects_invalid_inputs(kwargs: dict[str, object], message: str) -> None:
    values = {
        "source_id": "test_vendor",
        "metric_ids": ("ai_capex",),
        "start_date": date(2025, 1, 1),
        "end_date": date(2025, 1, 31),
        "requested_at": NOW,
    }
    values.update(kwargs)

    with pytest.raises(CapexFetchJobContractError, match=message):
        CapexFetchJobRequest(**values)


def test_fetch_job_contracts_do_not_import_strategy_order_or_schedulers() -> None:
    source = Path("api/data/capex_jobs.py").read_text()

    forbidden_terms = (
        "api.strategy",
        "api.brokers",
        "api.features.orders",
        "kis",
        "sqlite3",
        "requests",
        "httpx",
        "asyncio",
        "threading",
        "apscheduler",
        "celery",
    )
    assert not any(term in source for term in forbidden_terms)
