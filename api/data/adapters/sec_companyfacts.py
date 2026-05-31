from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from api.data.capex_models import RawCompanyMetricPoint


class SecCompanyFactsAdapterError(ValueError):
    pass


DEFAULT_TAG_MAPPING: dict[str, str] = {
    "PaymentsToAcquirePropertyPlantAndEquipment": "capital_expenditures_usd",
    "CapitalExpenditures": "capital_expenditures_usd",
    "Revenues": "revenue_usd",
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue_usd",
    "OperatingIncomeLoss": "operating_income_usd",
    "EarningsPerShareDiluted": "eps_diluted",
    "EarningsPerShareBasic": "eps_basic",
}


@dataclass(frozen=True)
class SecCompanyFactsParseResult:
    points: tuple[RawCompanyMetricPoint, ...]
    warnings: tuple[str, ...] = ()


@dataclass
class SecCompanyFactsAdapter:
    company_ciks: Mapping[str, str] = field(default_factory=dict)
    tag_mapping: Mapping[str, str] = field(default_factory=lambda: DEFAULT_TAG_MAPPING)
    http_client: Any | None = None
    user_agent: str | None = None
    base_url: str = "https://data.sec.gov/api/xbrl/companyfacts"
    timeout_seconds: int = 30
    source_id: str = "SEC_EDGAR_COMPANYFACTS"
    client_name: str = "sec_companyfacts"

    def list_metrics(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.tag_mapping.values())))

    def parse_companyfacts(
        self,
        payload: Mapping[str, Any],
        *,
        company_id: str | None = None,
        metric_ids: Sequence[str] | None = None,
        as_of: datetime | None = None,
    ) -> SecCompanyFactsParseResult:
        resolved_company_id = company_id or _company_id(payload)
        allowed_metrics = set(metric_ids) if metric_ids is not None else None
        facts = payload.get("facts")
        if not isinstance(facts, Mapping):
            raise SecCompanyFactsAdapterError("facts must be an object")
        us_gaap = facts.get("us-gaap")
        if not isinstance(us_gaap, Mapping):
            raise SecCompanyFactsAdapterError("facts.us-gaap must be an object")

        points: list[RawCompanyMetricPoint] = []
        found_metrics: set[str] = set()
        for tag, metric_id in self.tag_mapping.items():
            if allowed_metrics is not None and metric_id not in allowed_metrics:
                continue
            tag_payload = us_gaap.get(tag)
            if not isinstance(tag_payload, Mapping):
                continue
            units = tag_payload.get("units")
            if not isinstance(units, Mapping):
                continue
            found_metrics.add(metric_id)
            points.extend(
                self._points_for_tag(
                    units,
                    company_id=resolved_company_id,
                    metric_id=metric_id,
                    sec_tag=tag,
                    as_of=as_of,
                )
            )

        requested_metrics = allowed_metrics or set(self.tag_mapping.values())
        warnings = tuple(
            f"MISSING_SEC_TAG_FOR_METRIC:{metric_id}"
            for metric_id in sorted(requested_metrics - found_metrics)
        )
        return SecCompanyFactsParseResult(points=tuple(points), warnings=warnings)

    def fetch_company_metrics(
        self,
        *,
        company_ids: Sequence[str],
        metric_ids: Sequence[str],
        start_period: str | None = None,
        end_period: str | None = None,
        as_of: datetime | None = None,
    ) -> tuple[RawCompanyMetricPoint, ...]:
        rows: list[RawCompanyMetricPoint] = []
        for company_id in company_ids:
            payload = self._fetch_payload(company_id)
            result = self.parse_companyfacts(payload, company_id=company_id, metric_ids=metric_ids, as_of=as_of)
            rows.extend(
                point
                for point in result.points
                if (start_period is None or point.period >= start_period)
                and (end_period is None or point.period <= end_period)
            )
        return tuple(rows)

    def _points_for_tag(
        self,
        units: Mapping[str, Any],
        *,
        company_id: str,
        metric_id: str,
        sec_tag: str,
        as_of: datetime | None,
    ) -> tuple[RawCompanyMetricPoint, ...]:
        points: list[RawCompanyMetricPoint] = []
        for unit, values in units.items():
            if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
                continue
            for row in values:
                if not isinstance(row, Mapping):
                    continue
                value = _decimal_or_none(row.get("val"))
                if value is None:
                    continue
                filed = _optional_date(row.get("filed"))
                available_at = _available_at(filed or _date(row.get("end")))
                if as_of is not None and available_at > as_of:
                    continue
                period = _period(row)
                points.append(
                    RawCompanyMetricPoint(
                        source=self.source_id,
                        source_id="sec_companyfacts",
                        company_id=company_id,
                        metric_id=metric_id,
                        period=period,
                        value=value,
                        unit=str(unit),
                        available_at=available_at,
                        updated_at=available_at,
                        revision_id=str(row.get("accn")) if row.get("accn") else None,
                        source_priority=0,
                        confidence=1.0,
                        license_class="public",
                        attributes={
                            "sec_tag": sec_tag,
                            "fy": row.get("fy"),
                            "fp": row.get("fp"),
                            "form": row.get("form"),
                            "filed": filed.isoformat() if filed else None,
                            "start": row.get("start"),
                            "end": row.get("end"),
                            "frame": row.get("frame"),
                            "accn": row.get("accn"),
                        },
                    )
                )
        return tuple(points)

    def _fetch_payload(self, company_id: str) -> Mapping[str, Any]:
        if self.http_client is None:
            raise SecCompanyFactsAdapterError("http_client is required for live fetches")
        if not self.user_agent:
            raise SecCompanyFactsAdapterError("SEC user_agent is required for live fetches")
        cik = self.company_ciks.get(company_id)
        if not cik:
            raise SecCompanyFactsAdapterError(f"missing SEC CIK for company_id: {company_id}")
        url = f"{self.base_url}/CIK{str(cik).zfill(10)}.json"
        response = self.http_client.get(
            url,
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout_seconds,
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if getattr(response, "status_code", 200) >= 400:
            raise SecCompanyFactsAdapterError(f"HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise SecCompanyFactsAdapterError("response JSON must be an object")
        return payload


def _company_id(payload: Mapping[str, Any]) -> str:
    cik = payload.get("cik")
    if cik is not None:
        return f"CIK{str(cik).zfill(10)}"
    entity_name = payload.get("entityName")
    if isinstance(entity_name, str) and entity_name.strip():
        return entity_name.strip()
    raise SecCompanyFactsAdapterError("company_id or payload cik is required")


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, "", "."):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _period(row: Mapping[str, Any]) -> str:
    frame = row.get("frame")
    if isinstance(frame, str) and frame.strip():
        return frame
    fy = row.get("fy")
    fp = row.get("fp")
    if fy and fp:
        return f"{fy}{fp}"
    end = row.get("end")
    if end:
        return str(end)
    raise SecCompanyFactsAdapterError("SEC row period is required")


def _date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if not value:
        raise SecCompanyFactsAdapterError("date is required")
    return date.fromisoformat(str(value))


def _optional_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    return _date(value)


def _available_at(value: date) -> datetime:
    return datetime.combine(value, time(hour=0), tzinfo=UTC)
