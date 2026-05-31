from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from api.data.capex_jobs import CapexFetchJobResult, CapexFetchStatus
from api.data.capex_models import RawTimeSeriesPoint


class FredAlfredAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class FredAlfredSeries:
    metric_id: str
    series_id: str
    unit: str = "unknown"
    source_priority: int = 0
    license_class: str = "public"


@dataclass
class FredAlfredAdapter:
    series: Mapping[str, FredAlfredSeries | str]
    http_client: Any | None = None
    api_key: str | None = None
    base_url: str = "https://api.stlouisfed.org/fred/series/observations"
    timeout_seconds: int = 30
    source_id: str = "FRED_ALFRED"
    client_name: str = "fred_alfred"
    default_unit: str = "unknown"
    _series_by_metric: dict[str, FredAlfredSeries] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._series_by_metric = {
            metric_id: _series_spec(metric_id, spec, default_unit=self.default_unit)
            for metric_id, spec in self.series.items()
        }

    def list_metrics(self) -> tuple[str, ...]:
        return tuple(sorted(self._series_by_metric))

    def parse_observations(
        self,
        payload: Mapping[str, Any],
        *,
        metric_id: str,
        series_id: str | None = None,
        unit: str | None = None,
        source_priority: int = 0,
        license_class: str = "public",
        as_of: datetime | None = None,
    ) -> tuple[RawTimeSeriesPoint, ...]:
        rows = payload.get("observations")
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise FredAlfredAdapterError("observations must be a sequence")

        resolved_series_id = series_id or self._series_id(metric_id)
        resolved_unit = unit or self._unit(metric_id)
        points: list[RawTimeSeriesPoint] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            value = _decimal_or_none(row.get("value"))
            if value is None:
                continue
            observation_date = _date(row.get("date"))
            realtime_start = _optional_date(row.get("realtime_start"))
            realtime_end = _optional_date(row.get("realtime_end"))
            available_at = _available_at(realtime_start or observation_date)
            if as_of is not None and available_at > as_of:
                continue
            updated_at = _available_at(realtime_end) if realtime_end and realtime_end.year < 9999 else available_at
            revision_id = _revision_id(realtime_start, realtime_end)
            points.append(
                RawTimeSeriesPoint(
                    source=self.source_id,
                    source_id=resolved_series_id,
                    metric_id=metric_id,
                    observation_date=observation_date,
                    value=value,
                    unit=resolved_unit,
                    available_at=available_at,
                    updated_at=updated_at,
                    revision_id=revision_id,
                    source_priority=source_priority,
                    confidence=1.0,
                    license_class=license_class,
                    attributes={
                        "fred_series_id": resolved_series_id,
                        "realtime_start": realtime_start.isoformat() if realtime_start else None,
                        "realtime_end": realtime_end.isoformat() if realtime_end else None,
                    },
                )
            )
        return tuple(points)

    def fetch_time_series(
        self,
        *,
        metric_id: str,
        start: date,
        end: date,
        as_of: datetime | None = None,
    ) -> tuple[RawTimeSeriesPoint, ...]:
        points, result = self.fetch_time_series_with_result(metric_id=metric_id, start=start, end=end, as_of=as_of)
        if result.status is CapexFetchStatus.FAILED:
            raise FredAlfredAdapterError("; ".join(result.errors) or "FRED/ALFRED fetch failed")
        return points

    def fetch_time_series_with_result(
        self,
        *,
        metric_id: str,
        start: date,
        end: date,
        as_of: datetime | None = None,
        requested_at: datetime | None = None,
    ) -> tuple[tuple[RawTimeSeriesPoint, ...], CapexFetchJobResult]:
        requested_at = requested_at or datetime.now(tz=UTC)
        started_at = datetime.now(tz=UTC)
        try:
            payload = self._fetch_payload(metric_id=metric_id, start=start, end=end)
            spec = self._series_by_metric[metric_id]
            points = self.parse_observations(
                payload,
                metric_id=metric_id,
                series_id=spec.series_id,
                unit=spec.unit,
                source_priority=spec.source_priority,
                license_class=spec.license_class,
                as_of=as_of,
            )
            warnings = () if points else ("NO_ROWS_FETCHED",)
            status = CapexFetchStatus.SUCCESS if points else CapexFetchStatus.SKIPPED
            return points, CapexFetchJobResult(
                request_id=None,
                source_id=self.source_id,
                metric_ids=(metric_id,),
                status=status,
                dry_run=True,
                requested_at=requested_at,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                rows_fetched=len(points),
                rows_stored=0,
                warnings=warnings,
                errors=(),
            )
        except Exception as exc:
            return (), CapexFetchJobResult(
                request_id=None,
                source_id=self.source_id,
                metric_ids=(metric_id,),
                status=CapexFetchStatus.FAILED,
                dry_run=True,
                requested_at=requested_at,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                rows_fetched=0,
                rows_stored=0,
                warnings=("REVIEW_REQUIRED",),
                errors=(str(exc),),
            )

    def _fetch_payload(self, *, metric_id: str, start: date, end: date) -> Mapping[str, Any]:
        if self.http_client is None:
            raise FredAlfredAdapterError("http_client is required for live fetches")
        if metric_id not in self._series_by_metric:
            raise FredAlfredAdapterError(f"unknown metric_id: {metric_id}")
        spec = self._series_by_metric[metric_id]
        params: dict[str, Any] = {
            "series_id": spec.series_id,
            "observation_start": start.isoformat(),
            "observation_end": end.isoformat(),
            "file_type": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key
        response = self.http_client.get(self.base_url, params=params, timeout=self.timeout_seconds)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if getattr(response, "status_code", 200) >= 400:
            raise FredAlfredAdapterError(f"HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise FredAlfredAdapterError("response JSON must be an object")
        return payload

    def _series_id(self, metric_id: str) -> str:
        if metric_id not in self._series_by_metric:
            raise FredAlfredAdapterError(f"unknown metric_id: {metric_id}")
        return self._series_by_metric[metric_id].series_id

    def _unit(self, metric_id: str) -> str:
        if metric_id not in self._series_by_metric:
            return self.default_unit
        return self._series_by_metric[metric_id].unit


def _series_spec(metric_id: str, spec: FredAlfredSeries | str, *, default_unit: str) -> FredAlfredSeries:
    if isinstance(spec, FredAlfredSeries):
        return spec
    return FredAlfredSeries(metric_id=metric_id, series_id=str(spec), unit=default_unit)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, "", "."):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if not value:
        raise FredAlfredAdapterError("date is required")
    return date.fromisoformat(str(value))


def _optional_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    return _date(value)


def _available_at(value: date) -> datetime:
    return datetime.combine(value, time(hour=0), tzinfo=UTC)


def _revision_id(realtime_start: date | None, realtime_end: date | None) -> str | None:
    if realtime_start is None and realtime_end is None:
        return None
    start = realtime_start.isoformat() if realtime_start else ""
    end = realtime_end.isoformat() if realtime_end else ""
    return f"{start}:{end}"
