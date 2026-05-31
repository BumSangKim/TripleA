from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree

from api.data.capex_models import RawTimeSeriesPoint


class EcosAdapterError(ValueError):
    pass


@dataclass(frozen=True)
class EcosSeries:
    metric_id: str
    stat_code: str
    item_code: str
    frequency: str
    unit: str = "unknown"
    source_priority: int = 0
    license_class: str = "public"


@dataclass(frozen=True)
class EcosParseResult:
    points: tuple[RawTimeSeriesPoint, ...]
    warnings: tuple[str, ...] = ()


@dataclass
class EcosAdapter:
    series: Mapping[str, EcosSeries]
    http_client: Any | None = None
    api_key: str | None = None
    base_url: str = "https://ecos.bok.or.kr/api/StatisticSearch"
    timeout_seconds: int = 30
    source_id: str = "ECOS"
    client_name: str = "ecos"

    def list_metrics(self) -> tuple[str, ...]:
        return tuple(sorted(self.series))

    def parse_response(
        self,
        payload: Mapping[str, Any] | str | bytes,
        *,
        metric_id: str,
        stat_code: str | None = None,
        item_code: str | None = None,
        frequency: str | None = None,
        unit: str | None = None,
        as_of: datetime | None = None,
    ) -> EcosParseResult:
        spec = self.series.get(metric_id)
        resolved_frequency = (frequency or (spec.frequency if spec else "")).upper()
        if resolved_frequency not in {"D", "M"}:
            return EcosParseResult(points=(), warnings=(f"UNSUPPORTED_ECOS_FREQUENCY:{resolved_frequency or 'UNKNOWN'}",))

        resolved_stat_code = stat_code or (spec.stat_code if spec else "")
        resolved_item_code = item_code or (spec.item_code if spec else "")
        resolved_unit = unit or (spec.unit if spec else "unknown")
        rows = _rows(payload)
        points: list[RawTimeSeriesPoint] = []
        for row in rows:
            if resolved_stat_code and str(row.get("STAT_CODE", "")) != resolved_stat_code:
                continue
            if resolved_item_code and str(row.get("ITEM_CODE1", "")) != resolved_item_code:
                continue
            value = _decimal_or_none(row.get("DATA_VALUE"))
            if value is None:
                continue
            observation_date = _observation_date(str(row.get("TIME", "")), resolved_frequency)
            available_at = _available_at(row.get("AVAILABLE_AT") or row.get("available_at"), observation_date)
            if as_of is not None and available_at > as_of:
                continue
            points.append(
                RawTimeSeriesPoint(
                    source=self.source_id,
                    source_id=f"{resolved_stat_code}:{resolved_item_code}",
                    metric_id=metric_id,
                    observation_date=observation_date,
                    value=value,
                    unit=str(row.get("UNIT_NAME") or resolved_unit),
                    available_at=available_at,
                    updated_at=available_at,
                    revision_id=None,
                    source_priority=spec.source_priority if spec else 0,
                    confidence=1.0,
                    license_class=spec.license_class if spec else "public",
                    attributes={
                        "stat_code": row.get("STAT_CODE") or resolved_stat_code,
                        "stat_name": row.get("STAT_NAME"),
                        "item_code": row.get("ITEM_CODE1") or resolved_item_code,
                        "item_name": row.get("ITEM_NAME1"),
                        "frequency": resolved_frequency,
                        "time": row.get("TIME"),
                    },
                )
            )
        warnings = () if points else ("NO_ECOS_ROWS",)
        return EcosParseResult(points=tuple(points), warnings=warnings)

    def fetch_time_series(
        self,
        *,
        metric_id: str,
        start: date,
        end: date,
        as_of: datetime | None = None,
    ) -> tuple[RawTimeSeriesPoint, ...]:
        if metric_id not in self.series:
            raise EcosAdapterError(f"unknown metric_id: {metric_id}")
        payload = self._fetch_payload(self.series[metric_id], start=start, end=end)
        return self.parse_response(payload, metric_id=metric_id, as_of=as_of).points

    def _fetch_payload(self, spec: EcosSeries, *, start: date, end: date) -> Mapping[str, Any]:
        if self.http_client is None:
            raise EcosAdapterError("http_client is required for live fetches")
        if not self.api_key:
            raise EcosAdapterError("api_key is required for live fetches")
        url = "/".join(
            [
                self.base_url.rstrip("/"),
                self.api_key,
                "json",
                "kr",
                "1",
                "1000",
                spec.stat_code,
                spec.frequency.upper(),
                _format_date(start, spec.frequency),
                _format_date(end, spec.frequency),
                spec.item_code,
            ]
        )
        response = self.http_client.get(url, timeout=self.timeout_seconds)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if getattr(response, "status_code", 200) >= 400:
            raise EcosAdapterError(f"HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise EcosAdapterError("response JSON must be an object")
        return payload


def _rows(payload: Mapping[str, Any] | str | bytes) -> tuple[Mapping[str, Any], ...]:
    if isinstance(payload, Mapping):
        search = payload.get("StatisticSearch", payload)
        if not isinstance(search, Mapping):
            raise EcosAdapterError("StatisticSearch must be an object")
        row = search.get("row", [])
        if isinstance(row, Mapping):
            return (row,)
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
            raise EcosAdapterError("ECOS rows must be a sequence")
        return tuple(item for item in row if isinstance(item, Mapping))

    root = ElementTree.fromstring(payload)
    parsed: list[dict[str, str]] = []
    for row in root.findall(".//row"):
        parsed.append({child.tag: (child.text or "").strip() for child in row})
    return tuple(parsed)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, "", "-", "."):
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _observation_date(value: str, frequency: str) -> date:
    if frequency == "D":
        if len(value) != 8:
            raise EcosAdapterError("daily ECOS TIME must be YYYYMMDD")
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    if frequency == "M":
        if len(value) != 6:
            raise EcosAdapterError("monthly ECOS TIME must be YYYYMM")
        return date(int(value[:4]), int(value[4:6]), 1)
    raise EcosAdapterError(f"unsupported ECOS frequency: {frequency}")


def _available_at(value: Any, fallback: date) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time(hour=0), tzinfo=UTC)
    if value:
        text = str(value)
        if len(text) == 8 and text.isdigit():
            parsed = date(int(text[:4]), int(text[4:6]), int(text[6:8]))
            return datetime.combine(parsed, time(hour=0), tzinfo=UTC)
        parsed_dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed_dt if parsed_dt.tzinfo else parsed_dt.replace(tzinfo=UTC)
    return datetime.combine(fallback, time(hour=0), tzinfo=UTC)


def _format_date(value: date, frequency: str) -> str:
    if frequency.upper() == "D":
        return value.strftime("%Y%m%d")
    if frequency.upper() == "M":
        return value.strftime("%Y%m")
    return value.isoformat()
