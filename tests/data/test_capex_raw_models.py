from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from api.data.capex_models import (
    CapexRawDataModelError,
    DataQualityIssueRecord,
    RawCompanyMetricPoint,
    RawTimeSeriesPoint,
    SourceFetchLogRecord,
)


NOW = datetime(2026, 5, 31, 9, 0, tzinfo=UTC)


def test_raw_time_series_point_constructs_and_round_trips():
    point = RawTimeSeriesPoint(
        source="SEC_EDGAR_COMPANYFACTS",
        source_id="sec_companyfacts",
        metric_id="ai.capex.yoy",
        observation_date=date(2026, 3, 31),
        value=Decimal("0.18"),
        unit="year_over_year_change",
        available_at=NOW,
        updated_at=NOW,
        revision_id="v1",
        source_priority=1,
        confidence=0.9,
        license_class="public",
        attributes={"issuer": "sample"},
    )

    payload = point.to_dict()
    restored = RawTimeSeriesPoint.from_dict(payload)

    assert payload["available_at"] == NOW.isoformat()
    assert payload["value"] == "0.18"
    assert restored == point


def test_raw_company_metric_point_constructs_and_round_trips():
    point = RawCompanyMetricPoint(
        source="OPENDART",
        source_id="opendart",
        company_id="sample_bio_supplier",
        metric_id="company.order_backlog.growth",
        period="2026Q1",
        value="0.12",
        unit="year_over_year_change",
        available_at=NOW,
        updated_at=NOW,
        revision_id=None,
        source_priority=2,
        confidence=0.8,
        license_class="public",
    )

    assert point.value == Decimal("0.12")
    assert RawCompanyMetricPoint.from_dict(point.to_dict()) == point


def test_available_at_is_required():
    with pytest.raises(CapexRawDataModelError, match="available_at"):
        RawTimeSeriesPoint(
            source="SEC_EDGAR_COMPANYFACTS",
            source_id="sec_companyfacts",
            metric_id="ai.capex.yoy",
            observation_date=date(2026, 3, 31),
            value=Decimal("0.18"),
            unit="year_over_year_change",
            available_at=None,  # type: ignore[arg-type]
            updated_at=NOW,
        )


def test_fetch_log_and_quality_issue_records_preserve_audit_metadata():
    log = SourceFetchLogRecord(
        fetch_id="fetch-1",
        source_id="sec_companyfacts",
        started_at=NOW,
        finished_at=NOW,
        status="success",
        row_count=2,
        metric_ids=["ai.capex.yoy"],
        reason_codes=["FETCH_COMPLETED"],
        warnings=[],
    )
    issue = DataQualityIssueRecord(
        issue_id="issue-1",
        source_id="sec_companyfacts",
        metric_id="ai.capex.yoy",
        severity="WARNING",
        reason_code="MISSING_DATA",
        message="missing component",
        as_of_date=date(2026, 5, 31),
        available_at=NOW,
        updated_at=NOW,
        fallback_state="REVIEW_REQUIRED",
        confidence=0.0,
    )

    assert log.to_dict()["row_count"] == 2
    assert issue.to_dict()["fallback_state"] == "REVIEW_REQUIRED"
    assert issue.to_dict()["available_at"] == NOW.isoformat()


def test_quality_issue_rejects_non_conservative_fallback_state():
    with pytest.raises(CapexRawDataModelError, match="fallback_state"):
        DataQualityIssueRecord(
            issue_id="issue-1",
            source_id="sec_companyfacts",
            metric_id="ai.capex.yoy",
            severity="WARNING",
            reason_code="MISSING_DATA",
            message="missing component",
            as_of_date=date(2026, 5, 31),
            available_at=NOW,
            updated_at=NOW,
            fallback_state="BUY",
            confidence=0.0,
        )


def test_capex_raw_models_do_not_import_db_network_or_execution_layers():
    source = Path("api/data/capex_models.py").read_text(encoding="utf-8").lower()

    forbidden = ["sqlite3", "requests", "httpx", "urllib", "api.brokers", "api.features.orders", "api.strategy", "kis"]
    assert not [item for item in forbidden if item in source]
