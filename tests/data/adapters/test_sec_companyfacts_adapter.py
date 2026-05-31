from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from api.data.adapters.sec_companyfacts import SecCompanyFactsAdapter


FIXTURE = Path("tests/fixtures/data/sec_companyfacts/companyfacts_sample.json")


class FakeResponse:
    def __init__(self, payload: dict[str, object], status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[dict[str, object]] = []

    def get(self, url: str, *, headers: dict[str, str], timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        return self.response


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text())


def test_sec_fixture_parses_into_canonical_company_metrics() -> None:
    adapter = SecCompanyFactsAdapter()

    result = adapter.parse_companyfacts(load_fixture(), company_id="sample_ai_infra")

    metric_ids = {point.metric_id for point in result.points}
    assert "capital_expenditures_usd" in metric_ids
    assert "revenue_usd" in metric_ids
    assert "operating_income_usd" in metric_ids
    assert "eps_diluted" in metric_ids
    assert all(point.source == "SEC_EDGAR_COMPANYFACTS" for point in result.points)
    assert all(point.company_id == "sample_ai_infra" for point in result.points)


def test_filing_period_available_at_unit_and_value_are_preserved() -> None:
    adapter = SecCompanyFactsAdapter()

    result = adapter.parse_companyfacts(
        load_fixture(),
        company_id="sample_ai_infra",
        metric_ids=("capital_expenditures_usd",),
        as_of=datetime(2024, 5, 30, tzinfo=UTC),
    )

    q1_point = next(point for point in result.points if point.period == "CY2024Q1")
    assert q1_point.value == Decimal("260000000")
    assert q1_point.unit == "USD"
    assert q1_point.available_at == datetime(2024, 5, 8, tzinfo=UTC)
    assert q1_point.updated_at == datetime(2024, 5, 8, tzinfo=UTC)
    assert q1_point.revision_id == "0001234567-24-000020"
    assert q1_point.attributes["fy"] == 2024
    assert q1_point.attributes["fp"] == "Q1"
    assert q1_point.attributes["filed"] == "2024-05-08"


def test_as_of_filter_excludes_future_filing_rows() -> None:
    adapter = SecCompanyFactsAdapter()

    result = adapter.parse_companyfacts(
        load_fixture(),
        company_id="sample_ai_infra",
        metric_ids=("capital_expenditures_usd",),
        as_of=datetime(2024, 3, 1, tzinfo=UTC),
    )

    assert [point.period for point in result.points] == ["CY2023"]


def test_missing_tags_warn_and_do_not_infer_zero_rows() -> None:
    payload = load_fixture()
    adapter = SecCompanyFactsAdapter()

    result = adapter.parse_companyfacts(
        payload,
        company_id="sample_ai_infra",
        metric_ids=("company.book_to_bill",),
    )

    assert result.points == ()
    assert result.warnings == ("MISSING_SEC_TAG_FOR_METRIC:company.book_to_bill",)


def test_http_client_is_injected_and_not_called_until_fetch() -> None:
    client = FakeClient(FakeResponse(load_fixture()))
    adapter = SecCompanyFactsAdapter(
        company_ciks={"sample_ai_infra": "1234567"},
        http_client=client,
        user_agent="TripleA test contact@example.com",
    )

    assert client.calls == []

    rows = adapter.fetch_company_metrics(
        company_ids=("sample_ai_infra",),
        metric_ids=("revenue_usd",),
        as_of=datetime(2024, 5, 30, tzinfo=UTC),
    )

    assert len(rows) == 1
    assert len(client.calls) == 1
    assert client.calls[0]["headers"]["User-Agent"] == "TripleA test contact@example.com"
    assert client.calls[0]["url"].endswith("/CIK0001234567.json")


def test_adapter_does_not_import_live_execution_modules() -> None:
    source = Path("api/data/adapters/sec_companyfacts.py").read_text()

    forbidden_terms = (
        "api.brokers",
        "api.features.orders",
        "api.strategy",
        "submit_order",
        "place_order",
        "auto_execute",
        "requests",
        "httpx",
    )

    assert not any(term in source for term in forbidden_terms)
