from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree

from api.data.capex_models import RawCompanyMetricPoint


class OpenDartAdapterError(ValueError):
    pass


DEFAULT_ACCOUNT_MAPPING: dict[str, str] = {
    "매출액": "segment_revenue",
    "Revenue": "segment_revenue",
    "수주잔고": "order_backlog_disclosure",
    "Order Backlog": "order_backlog_disclosure",
    "소모품매출": "consumables_or_recurring_revenue",
    "Consumables Revenue": "consumables_or_recurring_revenue",
    "영업이익": "gross_margin_operating_margin",
    "Operating Income": "gross_margin_operating_margin",
}


@dataclass(frozen=True)
class OpenDartParseResult:
    points: tuple[RawCompanyMetricPoint, ...]
    warnings: tuple[str, ...] = ()


@dataclass
class OpenDartAdapter:
    corp_codes: Mapping[str, str] = field(default_factory=dict)
    account_mapping: Mapping[str, str] = field(default_factory=lambda: DEFAULT_ACCOUNT_MAPPING)
    http_client: Any | None = None
    api_key: str | None = None
    base_url: str = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    timeout_seconds: int = 30
    source_id: str = "OPENDART"
    client_name: str = "opendart"

    def list_metrics(self) -> tuple[str, ...]:
        return tuple(sorted(set(self.account_mapping.values())))

    def parse_corp_codes(self, payload: str | bytes | Mapping[str, Any]) -> dict[str, dict[str, str]]:
        if isinstance(payload, Mapping):
            rows = payload.get("list", [])
            if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
                raise OpenDartAdapterError("corp-code list must be a sequence")
            return {
                str(row.get("corp_code")): {
                    "corp_name": str(row.get("corp_name", "")),
                    "stock_code": str(row.get("stock_code", "")),
                    "modify_date": str(row.get("modify_date", "")),
                }
                for row in rows
                if isinstance(row, Mapping) and row.get("corp_code")
            }

        root = ElementTree.fromstring(payload)
        parsed: dict[str, dict[str, str]] = {}
        for item in root.findall(".//list"):
            corp_code = _xml_text(item, "corp_code")
            if not corp_code:
                continue
            parsed[corp_code] = {
                "corp_name": _xml_text(item, "corp_name"),
                "stock_code": _xml_text(item, "stock_code"),
                "modify_date": _xml_text(item, "modify_date"),
            }
        return parsed

    def parse_financial_statement(
        self,
        payload: Mapping[str, Any],
        *,
        company_id: str | None = None,
        metric_ids: Sequence[str] | None = None,
        as_of: datetime | None = None,
    ) -> OpenDartParseResult:
        rows = payload.get("list", [])
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            raise OpenDartAdapterError("financial statement list must be a sequence")

        requested_metrics = set(metric_ids) if metric_ids is not None else None
        points: list[RawCompanyMetricPoint] = []
        warnings: list[str] = []
        seen_metrics: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            account_name = str(row.get("account_nm", "")).strip()
            metric_id = self.account_mapping.get(account_name)
            if not metric_id:
                if requested_metrics is None:
                    warnings.append(f"UNMAPPED_OPENDART_ACCOUNT:{account_name or 'UNKNOWN'}")
                continue
            if requested_metrics is not None and metric_id not in requested_metrics:
                continue
            value = _decimal_or_none(row.get("thstrm_amount") or row.get("amount"))
            if value is None:
                continue
            filed = _optional_date(row.get("rcept_dt") or row.get("filing_date"))
            if filed is None:
                warnings.append(f"MISSING_OPENDART_FILING_DATE:{account_name}")
                continue
            available_at = _available_at(filed)
            if as_of is not None and available_at > as_of:
                continue
            company = company_id or str(row.get("corp_code") or row.get("stock_code") or "").strip()
            if not company:
                warnings.append(f"MISSING_OPENDART_COMPANY_ID:{account_name}")
                continue
            seen_metrics.add(metric_id)
            points.append(
                RawCompanyMetricPoint(
                    source=self.source_id,
                    source_id="opendart",
                    company_id=company,
                    metric_id=metric_id,
                    period=_period(row),
                    value=value,
                    unit=str(row.get("currency") or row.get("currency_code") or "KRW"),
                    available_at=available_at,
                    updated_at=available_at,
                    revision_id=str(row.get("rcept_no")) if row.get("rcept_no") else None,
                    source_priority=0,
                    confidence=1.0,
                    license_class="public",
                    attributes={
                        "corp_code": row.get("corp_code"),
                        "stock_code": row.get("stock_code"),
                        "report_code": row.get("reprt_code"),
                        "business_year": row.get("bsns_year"),
                        "filing_date": filed.isoformat(),
                        "account_name": account_name,
                        "financial_statement": row.get("fs_nm"),
                        "statement_name": row.get("sj_nm"),
                    },
                )
            )
        if requested_metrics is not None:
            warnings.extend(f"MISSING_OPENDART_METRIC:{metric_id}" for metric_id in sorted(requested_metrics - seen_metrics))
        return OpenDartParseResult(points=tuple(points), warnings=tuple(warnings))

    def fetch_company_metrics(
        self,
        *,
        company_ids: Sequence[str],
        metric_ids: Sequence[str],
        start_period: str | None = None,
        end_period: str | None = None,
        as_of: datetime | None = None,
    ) -> tuple[RawCompanyMetricPoint, ...]:
        points: list[RawCompanyMetricPoint] = []
        for company_id in company_ids:
            payload = self._fetch_payload(company_id)
            result = self.parse_financial_statement(payload, company_id=company_id, metric_ids=metric_ids, as_of=as_of)
            points.extend(
                point
                for point in result.points
                if (start_period is None or point.period >= start_period)
                and (end_period is None or point.period <= end_period)
            )
        return tuple(points)

    def _fetch_payload(self, company_id: str) -> Mapping[str, Any]:
        if self.http_client is None:
            raise OpenDartAdapterError("http_client is required for live fetches")
        if not self.api_key:
            raise OpenDartAdapterError("api_key is required for live fetches")
        corp_code = self.corp_codes.get(company_id)
        if not corp_code:
            raise OpenDartAdapterError(f"missing OpenDART corp_code for company_id: {company_id}")
        response = self.http_client.get(
            self.base_url,
            params={"crtfc_key": self.api_key, "corp_code": corp_code},
            timeout=self.timeout_seconds,
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if getattr(response, "status_code", 200) >= 400:
            raise OpenDartAdapterError(f"HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise OpenDartAdapterError("response JSON must be an object")
        return payload


def _xml_text(item: ElementTree.Element, tag: str) -> str:
    value = item.findtext(tag)
    return value.strip() if value else ""


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, "", "-", "."):
        return None
    cleaned = str(value).replace(",", "").replace(" ", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _period(row: Mapping[str, Any]) -> str:
    year = row.get("bsns_year")
    report_code = row.get("reprt_code")
    if year and report_code:
        return f"{year}:{report_code}"
    if year:
        return str(year)
    raise OpenDartAdapterError("OpenDART business year is required")


def _optional_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    return date.fromisoformat(text)


def _available_at(value: date) -> datetime:
    return datetime.combine(value, time(hour=0), tzinfo=UTC)
