from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from api.data.adapters.ports import (
    CapexInputAdapter,
    CompanyMetricAdapter,
    DataAdapterContractError,
    TimeSeriesPoint,
)


NOW = datetime(2026, 5, 31, 9, 0, tzinfo=UTC)


def _point(series_id: str = "ai_capex_yoy") -> TimeSeriesPoint:
    return TimeSeriesPoint(
        series_id=series_id,
        value=Decimal("0.18"),
        observation_date=date(2026, 3, 31),
        available_at=NOW,
        updated_at=NOW,
        source="fixture",
    )


def test_time_series_point_requires_point_in_time_metadata():
    point = _point()

    assert point.series_id == "ai_capex_yoy"
    assert point.value == Decimal("0.18")
    assert point.available_at == NOW
    assert point.updated_at == NOW
    assert point.source == "fixture"


def test_available_at_is_required():
    with pytest.raises(DataAdapterContractError, match="available_at"):
        TimeSeriesPoint(
            series_id="ai_capex_yoy",
            value=Decimal("0.18"),
            observation_date=date(2026, 3, 31),
            available_at=None,  # type: ignore[arg-type]
            updated_at=NOW,
            source="fixture",
        )


def test_capex_input_adapter_protocol_conformance_with_fake_adapter():
    class FakeCapexInputAdapter:
        adapter_name = "fixture"
        network_called = False

        def list_series(self):
            return ("ai_capex_yoy",)

        def fetch_series(self, series_id, *, start=None, end=None, as_of=None):
            return [_point(series_id)]

    adapter = FakeCapexInputAdapter()

    assert isinstance(adapter, CapexInputAdapter)
    assert adapter.list_series() == ("ai_capex_yoy",)
    assert adapter.fetch_series("ai_capex_yoy", as_of=NOW)[0].available_at == NOW
    assert adapter.network_called is False


def test_company_metric_adapter_protocol_conformance_with_fake_adapter():
    class FakeCompanyMetricAdapter:
        adapter_name = "fixture"
        network_called = False

        def list_metrics(self, company_id=None):
            return ("backlog_growth_yoy",)

        def fetch_metric(self, company_id, metric_id, *, start=None, end=None, as_of=None):
            return [_point(f"{company_id}:{metric_id}")]

    adapter = FakeCompanyMetricAdapter()

    assert isinstance(adapter, CompanyMetricAdapter)
    assert adapter.list_metrics("supplier-a") == ("backlog_growth_yoy",)
    point = adapter.fetch_metric("supplier-a", "backlog_growth_yoy", as_of=NOW)[0]
    assert point.series_id == "supplier-a:backlog_growth_yoy"
    assert adapter.network_called is False


def test_ports_do_not_import_network_or_broker_clients():
    from api.data.adapters import ports

    source = ports.__loader__.get_source(ports.__name__)  # type: ignore[union-attr]

    assert "requests" not in source
    assert "httpx" not in source
    assert "urllib" not in source
    assert "socket" not in source
    assert "api.brokers" not in source
    assert "kis" not in source.lower()
