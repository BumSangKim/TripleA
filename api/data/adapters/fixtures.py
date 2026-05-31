from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Mapping, Sequence

from api.data.adapters.ports import TimeSeriesPoint


FIXTURE_SOURCE = "capex_fixture"


def _dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 9, 0, tzinfo=UTC)


def _point(series_id: str, value: str, observed: date, available_at: datetime) -> TimeSeriesPoint:
    return TimeSeriesPoint(
        series_id=series_id,
        value=Decimal(value),
        observation_date=observed,
        available_at=available_at,
        updated_at=available_at,
        source=FIXTURE_SOURCE,
    )


DEFAULT_CAPEX_SERIES: Mapping[str, tuple[TimeSeriesPoint, ...]] = {
    "ai.capex.yoy": (
        _point("ai.capex.yoy", "0.18", date(2026, 3, 31), _dt(2026, 4, 30)),
        _point("ai.capex.yoy", "0.21", date(2026, 6, 30), _dt(2026, 7, 31)),
    ),
    "ai.token_proxy.growth": (
        _point("ai.token_proxy.growth", "0.34", date(2026, 3, 31), _dt(2026, 4, 15)),
        _point("ai.token_proxy.growth", "0.37", date(2026, 6, 30), _dt(2026, 7, 15)),
    ),
    "bio.capex.component.capacity_growth": (
        _point("bio.capex.component.capacity_growth", "0.11", date(2026, 3, 31), _dt(2026, 4, 20)),
        _point("bio.capex.component.capacity_growth", "0.13", date(2026, 6, 30), _dt(2026, 7, 20)),
    ),
    "bio.capex.component.backlog_growth": (
        _point("bio.capex.component.backlog_growth", "0.09", date(2026, 3, 31), _dt(2026, 4, 20)),
        _point("bio.capex.component.backlog_growth", "0.10", date(2026, 6, 30), _dt(2026, 7, 20)),
    ),
}


DEFAULT_COMPANY_METRICS: Mapping[str, tuple[TimeSeriesPoint, ...]] = {
    "sample_bio_supplier:segment_revenue_growth": (
        _point("sample_bio_supplier:segment_revenue_growth", "0.08", date(2026, 3, 31), _dt(2026, 4, 25)),
        _point("sample_bio_supplier:segment_revenue_growth", "0.12", date(2026, 6, 30), _dt(2026, 7, 25)),
    ),
    "sample_bio_supplier:order_backlog_growth": (
        _point("sample_bio_supplier:order_backlog_growth", "0.14", date(2026, 3, 31), _dt(2026, 4, 25)),
        _point("sample_bio_supplier:order_backlog_growth", "0.16", date(2026, 6, 30), _dt(2026, 7, 25)),
    ),
}


class FixtureCapexInputAdapter:
    adapter_name = "capex_fixture"

    def __init__(self, series: Mapping[str, Sequence[TimeSeriesPoint]] | None = None):
        self._series = {key: tuple(rows) for key, rows in (series or DEFAULT_CAPEX_SERIES).items()}

    def list_series(self) -> tuple[str, ...]:
        return tuple(sorted(self._series))

    def fetch_series(
        self,
        series_id: str,
        *,
        start: date | None = None,
        end: date | None = None,
        as_of: datetime | None = None,
    ) -> tuple[TimeSeriesPoint, ...]:
        return _filter_points(self._series.get(series_id, ()), start=start, end=end, as_of=as_of)


class FixtureCompanyMetricAdapter:
    adapter_name = "company_metric_fixture"

    def __init__(self, metrics: Mapping[str, Sequence[TimeSeriesPoint]] | None = None):
        self._metrics = {key: tuple(rows) for key, rows in (metrics or DEFAULT_COMPANY_METRICS).items()}

    def list_metrics(self, company_id: str | None = None) -> tuple[str, ...]:
        metrics = sorted(_split_metric_key(key)[1] for key in self._metrics if company_id is None or key.startswith(f"{company_id}:"))
        return tuple(metrics)

    def fetch_metric(
        self,
        company_id: str,
        metric_id: str,
        *,
        start: date | None = None,
        end: date | None = None,
        as_of: datetime | None = None,
    ) -> tuple[TimeSeriesPoint, ...]:
        return _filter_points(self._metrics.get(f"{company_id}:{metric_id}", ()), start=start, end=end, as_of=as_of)


def _filter_points(
    rows: Sequence[TimeSeriesPoint],
    *,
    start: date | None,
    end: date | None,
    as_of: datetime | None,
) -> tuple[TimeSeriesPoint, ...]:
    if as_of is None:
        return ()
    return tuple(
        point
        for point in rows
        if point.available_at <= as_of
        and (start is None or point.observation_date >= start)
        and (end is None or point.observation_date <= end)
    )


def _split_metric_key(key: str) -> tuple[str, str]:
    company_id, metric_id = key.split(":", 1)
    return company_id, metric_id
