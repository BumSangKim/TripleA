from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from api.data.adapters.ecos import EcosAdapter, EcosSeries


DAILY_FIXTURE = Path("tests/fixtures/data/ecos/statistic_search_daily.json")
MONTHLY_FIXTURE = Path("tests/fixtures/data/ecos/statistic_search_monthly.xml")


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

    def get(self, url: str, *, timeout: int) -> FakeResponse:
        self.calls.append({"url": url, "timeout": timeout})
        return self.response


def adapter() -> EcosAdapter:
    return EcosAdapter(
        series={
            "macro.fx.usdkrw": EcosSeries(
                metric_id="macro.fx.usdkrw",
                stat_code="731Y001",
                item_code="0000001",
                frequency="D",
                unit="KRW_per_USD",
            ),
            "macro.rate.level": EcosSeries(
                metric_id="macro.rate.level",
                stat_code="722Y001",
                item_code="0101000",
                frequency="M",
                unit="percent",
            ),
        }
    )


def test_ecos_json_fixture_parses_daily_points() -> None:
    payload = json.loads(DAILY_FIXTURE.read_text())

    result = adapter().parse_response(payload, metric_id="macro.fx.usdkrw")

    assert len(result.points) == 2
    assert result.points[0].source == "ECOS"
    assert result.points[0].source_id == "731Y001:0000001"
    assert result.points[0].metric_id == "macro.fx.usdkrw"
    assert result.points[0].observation_date == date(2024, 5, 1)
    assert result.points[0].available_at == datetime(2024, 5, 2, tzinfo=UTC)
    assert result.points[0].value == Decimal("1375.50")
    assert result.points[0].attributes["frequency"] == "D"


def test_ecos_xml_fixture_parses_monthly_points() -> None:
    result = adapter().parse_response(MONTHLY_FIXTURE.read_text(), metric_id="macro.rate.level")

    assert len(result.points) == 1
    point = result.points[0]
    assert point.observation_date == date(2024, 5, 1)
    assert point.available_at == datetime(2024, 6, 1, tzinfo=UTC)
    assert point.unit == "%"
    assert point.attributes["frequency"] == "M"


def test_as_of_filter_excludes_unavailable_rows() -> None:
    payload = json.loads(DAILY_FIXTURE.read_text())

    result = adapter().parse_response(
        payload,
        metric_id="macro.fx.usdkrw",
        as_of=datetime(2024, 5, 2, 12, tzinfo=UTC),
    )

    assert [point.observation_date for point in result.points] == [date(2024, 5, 1)]


def test_unsupported_frequency_is_conservative() -> None:
    payload = json.loads(DAILY_FIXTURE.read_text())

    result = adapter().parse_response(
        payload,
        metric_id="macro.fx.usdkrw",
        frequency="W",
    )

    assert result.points == ()
    assert result.warnings == ("UNSUPPORTED_ECOS_FREQUENCY:W",)


def test_http_client_is_injected_and_not_called_until_fetch() -> None:
    payload = json.loads(DAILY_FIXTURE.read_text())
    client = FakeClient(FakeResponse(payload))
    client_adapter = EcosAdapter(series=adapter().series, http_client=client, api_key="test-key")

    assert client.calls == []

    rows = client_adapter.fetch_time_series(
        metric_id="macro.fx.usdkrw",
        start=date(2024, 5, 1),
        end=date(2024, 5, 2),
        as_of=datetime(2024, 5, 5, tzinfo=UTC),
    )

    assert len(rows) == 2
    assert len(client.calls) == 1
    assert "/test-key/json/kr/1/1000/731Y001/D/20240501/20240502/0000001" in client.calls[0]["url"]


def test_adapter_does_not_import_live_execution_modules() -> None:
    source = Path("api/data/adapters/ecos.py").read_text()

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
