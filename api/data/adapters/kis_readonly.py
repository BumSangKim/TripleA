from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

from api.data.capex_models import RawCompanyMetricPoint, RawTimeSeriesPoint


class KisReadOnlyAdapterError(ValueError):
    pass


DOMESTIC_QUOTE_ENDPOINT = "/uapi/domestic-stock/v1/quotations/inquire-price"
DOMESTIC_FUNDAMENTAL_ENDPOINT = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
KIS_READONLY_ENDPOINTS = frozenset({DOMESTIC_QUOTE_ENDPOINT, DOMESTIC_FUNDAMENTAL_ENDPOINT})
_BLOCKED_ENDPOINT_FRAGMENTS = ("trading", "inquire-balance", "order", "execution", "account")

FUNDAMENTAL_METRICS = {
    "per": "company.valuation.per",
    "pbr": "company.valuation.pbr",
    "eps": "company.valuation.eps",
    "bps": "company.valuation.bps",
}


@dataclass
class KisReadOnlyMarketAdapter:
    transport: Any | None = None
    token_provider: Callable[[], str] | None = None
    base_url: str = ""
    timeout_seconds: int = 10
    source_id: str = "KIS_READONLY_MARKET_DATA"
    client_name: str = "kis_readonly_market_data"

    def parse_quote_response(
        self,
        payload: Mapping[str, Any],
        *,
        symbol: str,
        market: str = "KRX",
        fetched_at: datetime | None = None,
    ) -> RawTimeSeriesPoint:
        output = _output(payload)
        price = _decimal(output.get("stck_prpr") or output.get("prpr"))
        if price <= 0:
            raise KisReadOnlyAdapterError("KIS quote response missing positive price")
        observed = _trade_date(output.get("stck_bsop_date"), fallback=fetched_at)
        available_at = fetched_at or datetime.now(tz=UTC)
        return RawTimeSeriesPoint(
            source=self.source_id,
            source_id=symbol,
            metric_id="market.price.close",
            observation_date=observed,
            value=price,
            unit="KRW",
            available_at=available_at,
            updated_at=available_at,
            revision_id=None,
            source_priority=0,
            confidence=1.0,
            license_class="broker_readonly",
            attributes={
                "symbol": symbol,
                "market": market,
                "trade_date": observed.isoformat(),
                "price_field": "stck_prpr" if output.get("stck_prpr") is not None else "prpr",
                "raw_status": payload.get("rt_cd"),
            },
        )

    def parse_fundamental_response(
        self,
        payload: Mapping[str, Any],
        *,
        company_id: str,
        fetched_at: datetime | None = None,
    ) -> tuple[RawCompanyMetricPoint, ...]:
        output = _output(payload)
        observed = _trade_date(output.get("stck_bsop_date"), fallback=fetched_at)
        available_at = fetched_at or datetime.combine(observed, time(hour=0), tzinfo=UTC)
        points: list[RawCompanyMetricPoint] = []
        for field_name, metric_id in FUNDAMENTAL_METRICS.items():
            value = _decimal_or_none(output.get(field_name))
            if value is None:
                continue
            points.append(
                RawCompanyMetricPoint(
                    source=self.source_id,
                    source_id=company_id,
                    company_id=company_id,
                    metric_id=metric_id,
                    period=observed.isoformat(),
                    value=value,
                    unit="ratio" if field_name in {"per", "pbr"} else "KRW",
                    available_at=available_at,
                    updated_at=available_at,
                    revision_id=None,
                    source_priority=0,
                    confidence=1.0,
                    license_class="broker_readonly",
                    attributes={
                        "field_name": field_name,
                        "trade_date": observed.isoformat(),
                        "raw_status": payload.get("rt_cd"),
                    },
                )
            )
        return tuple(points)

    def fetch_quote(self, *, symbol: str, market: str = "KRX") -> RawTimeSeriesPoint:
        payload = self._readonly_get(
            DOMESTIC_QUOTE_ENDPOINT,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
            },
        )
        return self.parse_quote_response(payload, symbol=symbol, market=market)

    def fetch_fundamentals(self, *, symbol: str) -> tuple[RawCompanyMetricPoint, ...]:
        payload = self._readonly_get(
            DOMESTIC_FUNDAMENTAL_ENDPOINT,
            params={
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": symbol,
            },
        )
        return self.parse_fundamental_response(payload, company_id=symbol)

    def _readonly_get(self, endpoint: str, *, params: Mapping[str, Any]) -> Mapping[str, Any]:
        ensure_readonly_endpoint(endpoint)
        if self.transport is None:
            raise KisReadOnlyAdapterError("transport is required for live read-only fetches")
        token = self.token_provider() if self.token_provider else ""
        headers = {"authorization": f"Bearer {token}"} if token else {}
        response = self.transport.get(
            f"{self.base_url.rstrip('/')}{endpoint}",
            headers=headers,
            params=dict(params),
            timeout=self.timeout_seconds,
        )
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if getattr(response, "status_code", 200) >= 400:
            raise KisReadOnlyAdapterError(f"HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise KisReadOnlyAdapterError("KIS response JSON must be an object")
        return payload


def ensure_readonly_endpoint(endpoint: str) -> None:
    normalized = endpoint.lower()
    if endpoint not in KIS_READONLY_ENDPOINTS:
        raise KisReadOnlyAdapterError("KIS endpoint is not in the read-only allowlist")
    if any(fragment in normalized for fragment in _BLOCKED_ENDPOINT_FRAGMENTS):
        raise KisReadOnlyAdapterError("KIS endpoint is blocked by read-only guardrail")


def _output(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    if str(payload.get("rt_cd", "0")).strip() not in {"", "0"}:
        raise KisReadOnlyAdapterError(str(payload.get("msg1") or "KIS read-only request failed"))
    output = payload.get("output") or {}
    if isinstance(output, list):
        output = output[0] if output else {}
    if not isinstance(output, Mapping):
        raise KisReadOnlyAdapterError("KIS output must be an object")
    return output


def _decimal(value: Any) -> Decimal:
    parsed = _decimal_or_none(value)
    if parsed is None:
        return Decimal("0")
    return parsed


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, "", "-", "."):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _trade_date(value: Any, *, fallback: datetime | None) -> date:
    if value:
        text = str(value)
        if len(text) == 8 and text.isdigit():
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        return date.fromisoformat(text)
    if fallback:
        return fallback.date()
    raise KisReadOnlyAdapterError("KIS response missing trade date")
