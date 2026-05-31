from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from api.data.adapters.opendart import OpenDartAdapter


CORP_CODE_FIXTURE = Path("tests/fixtures/data/opendart/corp_code_sample.xml")
FINANCIAL_FIXTURE = Path("tests/fixtures/data/opendart/financial_statement_sample.json")


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

    def get(self, url: str, *, params: dict[str, object], timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return self.response


def load_financial_fixture() -> dict[str, object]:
    return json.loads(FINANCIAL_FIXTURE.read_text())


def test_corp_code_xml_fixture_parses() -> None:
    adapter = OpenDartAdapter()

    parsed = adapter.parse_corp_codes(CORP_CODE_FIXTURE.read_text())

    assert parsed["00126380"]["corp_name"] == "샘플바이오"
    assert parsed["00126380"]["stock_code"] == "005930"
    assert parsed["00999999"]["stock_code"] == ""


def test_financial_statement_fixture_parses_into_company_metrics() -> None:
    adapter = OpenDartAdapter()

    result = adapter.parse_financial_statement(load_financial_fixture(), company_id="sample_bio_kr")

    metric_ids = {point.metric_id for point in result.points}
    assert "segment_revenue" in metric_ids
    assert "order_backlog_disclosure" in metric_ids
    assert "gross_margin_operating_margin" in metric_ids
    assert all(point.source == "OPENDART" for point in result.points)
    assert all(point.company_id == "sample_bio_kr" for point in result.points)


def test_filing_date_period_account_name_and_unit_are_preserved() -> None:
    adapter = OpenDartAdapter()

    result = adapter.parse_financial_statement(
        load_financial_fixture(),
        company_id="sample_bio_kr",
        metric_ids=("order_backlog_disclosure",),
        as_of=datetime(2024, 5, 20, tzinfo=UTC),
    )

    point = result.points[0]
    assert point.value == Decimal("1250000000000")
    assert point.period == "2024:11013"
    assert point.unit == "KRW"
    assert point.available_at == datetime(2024, 5, 15, tzinfo=UTC)
    assert point.updated_at == datetime(2024, 5, 15, tzinfo=UTC)
    assert point.revision_id == "20240515000001"
    assert point.attributes["report_code"] == "11013"
    assert point.attributes["business_year"] == "2024"
    assert point.attributes["filing_date"] == "2024-05-15"
    assert point.attributes["account_name"] == "수주잔고"


def test_as_of_filter_excludes_future_filings() -> None:
    adapter = OpenDartAdapter()

    result = adapter.parse_financial_statement(
        load_financial_fixture(),
        company_id="sample_bio_kr",
        metric_ids=("segment_revenue",),
        as_of=datetime(2024, 5, 1, tzinfo=UTC),
    )

    assert result.points == ()
    assert result.warnings == ("MISSING_OPENDART_METRIC:segment_revenue",)


def test_missing_metric_mapping_is_conservative() -> None:
    adapter = OpenDartAdapter(account_mapping={})

    result = adapter.parse_financial_statement(load_financial_fixture(), company_id="sample_bio_kr")

    assert result.points == ()
    assert "UNMAPPED_OPENDART_ACCOUNT:매출액" in result.warnings
    assert "UNMAPPED_OPENDART_ACCOUNT:수주잔고" in result.warnings


def test_http_client_is_injected_and_not_called_until_fetch() -> None:
    client = FakeClient(FakeResponse(load_financial_fixture()))
    adapter = OpenDartAdapter(
        corp_codes={"sample_bio_kr": "00126380"},
        http_client=client,
        api_key="test-key",
    )

    assert client.calls == []

    rows = adapter.fetch_company_metrics(
        company_ids=("sample_bio_kr",),
        metric_ids=("segment_revenue",),
        as_of=datetime(2024, 5, 20, tzinfo=UTC),
    )

    assert len(rows) == 1
    assert len(client.calls) == 1
    assert client.calls[0]["params"]["corp_code"] == "00126380"
    assert client.calls[0]["params"]["crtfc_key"] == "test-key"


def test_adapter_does_not_import_live_execution_modules() -> None:
    source = Path("api/data/adapters/opendart.py").read_text()

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
