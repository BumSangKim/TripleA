from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from api.data.adapters.fred_alfred import FredAlfredAdapter, FredAlfredAdapterError, FredAlfredSeries
from api.data.capex_jobs import CapexFetchStatus


FIXTURE = Path("tests/fixtures/data/fred_alfred/observations.json")


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


def load_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text())


def test_fixture_json_parses_into_canonical_points() -> None:
    adapter = FredAlfredAdapter(
        series={
            "macro.rate.level": FredAlfredSeries(
                metric_id="macro.rate.level",
                series_id="FEDFUNDS",
                unit="percent",
            )
        }
    )

    points = adapter.parse_observations(load_fixture(), metric_id="macro.rate.level")

    assert len(points) == 2
    assert points[0].source == "FRED_ALFRED"
    assert points[0].source_id == "FEDFUNDS"
    assert points[0].metric_id == "macro.rate.level"
    assert points[0].observation_date == date(2024, 1, 1)
    assert points[0].value == Decimal("5.33")
    assert points[0].unit == "percent"


def test_vintage_availability_fields_are_preserved_and_filterable() -> None:
    adapter = FredAlfredAdapter(series={"macro.rate.level": "FEDFUNDS"})

    points = adapter.parse_observations(
        load_fixture(),
        metric_id="macro.rate.level",
        as_of=datetime(2024, 6, 15, tzinfo=UTC),
    )

    assert len(points) == 1
    assert points[0].available_at == datetime(2024, 6, 1, tzinfo=UTC)
    assert points[0].updated_at == datetime(2024, 6, 30, tzinfo=UTC)
    assert points[0].revision_id == "2024-06-01:2024-06-30"
    assert points[0].attributes["realtime_start"] == "2024-06-01"
    assert points[0].attributes["realtime_end"] == "2024-06-30"


def test_http_client_is_injected_and_not_called_until_fetch() -> None:
    client = FakeClient(FakeResponse(load_fixture()))
    adapter = FredAlfredAdapter(series={"macro.rate.level": "FEDFUNDS"}, http_client=client)

    assert client.calls == []

    points = adapter.fetch_time_series(
        metric_id="macro.rate.level",
        start=date(2024, 1, 1),
        end=date(2024, 3, 31),
        as_of=datetime(2024, 7, 15, tzinfo=UTC),
    )

    assert len(points) == 2
    assert len(client.calls) == 1
    assert client.calls[0]["params"]["series_id"] == "FEDFUNDS"


def test_http_errors_map_to_fetch_result_errors() -> None:
    client = FakeClient(FakeResponse({"error": "bad"}, status_code=500))
    adapter = FredAlfredAdapter(series={"macro.rate.level": "FEDFUNDS"}, http_client=client)

    points, result = adapter.fetch_time_series_with_result(
        metric_id="macro.rate.level",
        start=date(2024, 1, 1),
        end=date(2024, 3, 31),
        requested_at=datetime(2024, 7, 15, tzinfo=UTC),
    )

    assert points == ()
    assert result.status is CapexFetchStatus.FAILED
    assert result.dry_run is True
    assert result.rows_stored == 0
    assert result.warnings == ("REVIEW_REQUIRED",)
    assert result.errors


def test_fetch_without_http_client_is_conservative_error() -> None:
    adapter = FredAlfredAdapter(series={"macro.rate.level": "FEDFUNDS"})

    points, result = adapter.fetch_time_series_with_result(
        metric_id="macro.rate.level",
        start=date(2024, 1, 1),
        end=date(2024, 3, 31),
        requested_at=datetime(2024, 7, 15, tzinfo=UTC),
    )

    assert points == ()
    assert result.status is CapexFetchStatus.FAILED
    assert "http_client is required" in result.errors[0]


def test_fetch_time_series_raises_contract_error_on_failed_result() -> None:
    adapter = FredAlfredAdapter(series={"macro.rate.level": "FEDFUNDS"})

    try:
        adapter.fetch_time_series(
            metric_id="macro.rate.level",
            start=date(2024, 1, 1),
            end=date(2024, 3, 31),
        )
    except FredAlfredAdapterError as exc:
        assert "http_client is required" in str(exc)
    else:
        raise AssertionError("expected conservative adapter error")


def test_adapter_does_not_import_live_execution_modules() -> None:
    source = Path("api/data/adapters/fred_alfred.py").read_text()

    forbidden_terms = (
        "api.brokers",
        "api.features.orders",
        "api.strategy",
        "submit_order",
        "place_order",
        "auto_execute",
    )

    assert not any(term in source for term in forbidden_terms)
