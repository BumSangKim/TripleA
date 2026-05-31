from __future__ import annotations

import ast
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from api.data.adapters.kis_readonly import (
    DOMESTIC_FUNDAMENTAL_ENDPOINT,
    DOMESTIC_QUOTE_ENDPOINT,
    KIS_READONLY_ENDPOINTS,
    KisReadOnlyAdapterError,
    KisReadOnlyMarketAdapter,
    ensure_readonly_endpoint,
)


QUOTE_FIXTURE = Path("tests/fixtures/data/kis_readonly/quote_response.json")
FUNDAMENTAL_FIXTURE = Path("tests/fixtures/data/kis_readonly/fundamental_response.json")


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeTransport:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, object],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "params": params, "timeout": timeout})
        return self.response


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def test_price_fixture_parses_into_raw_time_series_point() -> None:
    adapter = KisReadOnlyMarketAdapter()
    fetched_at = datetime(2024, 5, 31, 6, tzinfo=UTC)

    point = adapter.parse_quote_response(load_json(QUOTE_FIXTURE), symbol="005930", fetched_at=fetched_at)

    assert point.source == "KIS_READONLY_MARKET_DATA"
    assert point.source_id == "005930"
    assert point.metric_id == "market.price.close"
    assert point.observation_date.isoformat() == "2024-05-31"
    assert point.value == Decimal("73500")
    assert point.unit == "KRW"
    assert point.available_at == fetched_at


def test_fundamental_fixture_parses_into_company_metric_points() -> None:
    adapter = KisReadOnlyMarketAdapter()
    fetched_at = datetime(2024, 5, 31, 6, tzinfo=UTC)

    points = adapter.parse_fundamental_response(
        load_json(FUNDAMENTAL_FIXTURE),
        company_id="005930",
        fetched_at=fetched_at,
    )

    metrics = {point.metric_id: point for point in points}
    assert metrics["company.valuation.per"].value == Decimal("15.2")
    assert metrics["company.valuation.pbr"].unit == "ratio"
    assert metrics["company.valuation.eps"].value == Decimal("4800")
    assert metrics["company.valuation.bps"].period == "2024-05-31"
    assert all(point.available_at == fetched_at for point in points)


def test_readonly_endpoint_allowlist_and_blocking() -> None:
    assert KIS_READONLY_ENDPOINTS == {DOMESTIC_QUOTE_ENDPOINT, DOMESTIC_FUNDAMENTAL_ENDPOINT}
    ensure_readonly_endpoint(DOMESTIC_QUOTE_ENDPOINT)
    ensure_readonly_endpoint(DOMESTIC_FUNDAMENTAL_ENDPOINT)

    with pytest.raises(KisReadOnlyAdapterError):
        ensure_readonly_endpoint("/uapi/domestic-stock/v1/trading/inquire-balance")


def test_transport_and_token_are_injected_and_not_called_until_fetch() -> None:
    transport = FakeTransport(FakeResponse(load_json(QUOTE_FIXTURE)))
    adapter = KisReadOnlyMarketAdapter(
        transport=transport,
        token_provider=lambda: "fake-token",
        base_url="https://example.invalid",
    )

    assert transport.calls == []

    point = adapter.fetch_quote(symbol="005930")

    assert point.value == Decimal("73500")
    assert len(transport.calls) == 1
    assert transport.calls[0]["headers"]["authorization"] == "Bearer fake-token"
    assert transport.calls[0]["url"].endswith(DOMESTIC_QUOTE_ENDPOINT)


def test_adapter_does_not_import_order_balance_or_execution_modules() -> None:
    tree = ast.parse(Path("api/data/adapters/kis_readonly.py").read_text())
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    forbidden_imports = ("api.brokers", "api.features.orders", "api.strategy")
    assert not any(module.startswith(forbidden_imports) for module in imports)


def test_adapter_source_has_no_order_submission_surface() -> None:
    source = Path("api/data/adapters/kis_readonly.py").read_text()
    forbidden_terms = ("submit_order", "place_order", "send_order", "create_order", "password")

    assert not any(term in source for term in forbidden_terms)
