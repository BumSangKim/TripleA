from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from api.data.capex_models import RawCompanyMetricPoint, RawTimeSeriesPoint
from api.data.capex_repository import SqliteCapexRawDataRepository
from api.data.capex_snapshot_builder import CapexRawSnapshotBuilder


DECISION_TIME = datetime(2024, 5, 31, 23, 59, tzinfo=UTC)


def make_repo() -> SqliteCapexRawDataRepository:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return SqliteCapexRawDataRepository(conn)


def point(
    metric_id: str,
    observed: date,
    value: str,
    *,
    available_at: datetime,
    updated_at: datetime | None = None,
    revision_id: str | None = None,
) -> RawTimeSeriesPoint:
    return RawTimeSeriesPoint(
        source="ECOS",
        source_id="731Y001:0000001",
        metric_id=metric_id,
        observation_date=observed,
        value=Decimal(value),
        unit="KRW_per_USD",
        available_at=available_at,
        updated_at=updated_at or available_at,
        revision_id=revision_id,
    )


def company_point(period: str, value: str, *, available_at: datetime) -> RawCompanyMetricPoint:
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


def test_latest_available_value_is_selected() -> None:
    repo = make_repo()
    repo.upsert_time_series(
        [
            point(
                "macro.fx.usdkrw",
                date(2024, 5, 1),
                "1370",
                available_at=datetime(2024, 5, 2, tzinfo=UTC),
                revision_id="old",
            ),
            point(
                "macro.fx.usdkrw",
                date(2024, 5, 30),
                "1385",
                available_at=datetime(2024, 5, 31, tzinfo=UTC),
                revision_id="new",
            ),
        ]
    )

    snapshot = CapexRawSnapshotBuilder(repository=repo).build(
        decision_time=DECISION_TIME,
        metric_ids=("macro.fx.usdkrw",),
    )

    selected = snapshot.points["macro.fx.usdkrw"]
    assert selected.value == 1385.0
    assert selected.revision_id == "new"
    assert snapshot.point_metadata["macro.fx.usdkrw"].source_id == "731Y001:0000001"
    assert snapshot.point_metadata["macro.fx.usdkrw"].available_at == datetime(2024, 5, 31, tzinfo=UTC)


def test_future_available_row_is_excluded() -> None:
    repo = make_repo()
    repo.upsert_time_series(
        [
            point("macro.rate.level", date(2024, 5, 1), "3.5", available_at=datetime(2024, 5, 15, tzinfo=UTC)),
            point("macro.rate.level", date(2024, 6, 1), "9.9", available_at=datetime(2024, 6, 2, tzinfo=UTC)),
        ]
    )

    snapshot = CapexRawSnapshotBuilder(repository=repo).build(
        decision_time=DECISION_TIME,
        metric_ids=("macro.rate.level",),
    )

    assert snapshot.points["macro.rate.level"].value == 3.5
    assert snapshot.get_available("macro.rate.level").available_at <= DECISION_TIME


def test_missing_metric_produces_warning_and_quality_metadata() -> None:
    repo = make_repo()

    snapshot = CapexRawSnapshotBuilder(repository=repo).build(
        decision_time=DECISION_TIME,
        metric_ids=("macro.fx.usdkrw",),
    )

    assert "macro.fx.usdkrw" not in snapshot.points
    assert snapshot.missing_metrics == ("macro.fx.usdkrw",)
    assert snapshot.warnings[0].code == "MISSING_RAW_METRIC"
    quality = snapshot.point_metadata["macro.fx.usdkrw"].quality
    assert quality.missing_ratio == 1.0
    assert quality.conservative_action == "REVIEW_REQUIRED"


def test_stale_quality_flag_works() -> None:
    repo = make_repo()
    repo.upsert_time_series(
        [
            point(
                "macro.fx.usdkrw",
                date(2024, 1, 1),
                "1300",
                available_at=datetime(2024, 1, 2, tzinfo=UTC),
                updated_at=datetime(2024, 1, 2, tzinfo=UTC),
            )
        ]
    )

    snapshot = CapexRawSnapshotBuilder(
        repository=repo,
        stale_after_days_by_metric={"macro.fx.usdkrw": 7},
    ).build(decision_time=DECISION_TIME, metric_ids=("macro.fx.usdkrw",))

    quality = snapshot.point_metadata["macro.fx.usdkrw"].quality
    assert quality.is_stale is True
    assert quality.conservative_action == "HOLD"


def test_company_metric_snapshot_key_preserves_metadata() -> None:
    repo = make_repo()
    repo.upsert_company_metrics([company_point("CY2024Q1", "260", available_at=datetime(2024, 5, 8, tzinfo=UTC))])

    snapshot = CapexRawSnapshotBuilder(repository=repo).build(
        decision_time=DECISION_TIME,
        metric_ids=(),
        company_metric_ids={"sample_ai": ("capital_expenditures_usd",)},
    )

    key = "sample_ai:capital_expenditures_usd"
    assert snapshot.points[key].value == 260.0
    assert snapshot.point_metadata[key].unit == "USD"
    assert snapshot.point_metadata[key].revision_id == "rev-1"


def test_snapshot_builder_has_no_execution_or_network_imports() -> None:
    source = Path("api/data/capex_snapshot_builder.py").read_text()
    forbidden_terms = (
        "api.brokers",
        "api.features.orders",
        "api.strategy",
        "requests",
        "httpx",
        "submit_order",
        "place_order",
    )

    assert not any(term in source for term in forbidden_terms)
