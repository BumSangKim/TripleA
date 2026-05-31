from __future__ import annotations

from datetime import UTC, date, datetime

from api.data.adapters.fixtures import FixtureCapexInputAdapter, FixtureCompanyMetricAdapter
from api.data.adapters.ports import CapexInputAdapter, CompanyMetricAdapter


APRIL_DECISION = datetime(2026, 5, 31, 9, 0, tzinfo=UTC)
JULY_DECISION = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def test_fixture_adapter_returns_available_data_at_decision_time():
    adapter = FixtureCapexInputAdapter()

    rows = adapter.fetch_series("ai.capex.yoy", as_of=APRIL_DECISION)

    assert isinstance(adapter, CapexInputAdapter)
    assert len(rows) == 1
    assert rows[0].observation_date == date(2026, 3, 31)
    assert rows[0].available_at <= APRIL_DECISION


def test_fixture_adapter_excludes_future_available_rows():
    adapter = FixtureCapexInputAdapter()

    early_rows = adapter.fetch_series("ai.capex.yoy", as_of=APRIL_DECISION)
    later_rows = adapter.fetch_series("ai.capex.yoy", as_of=JULY_DECISION)

    assert len(early_rows) == 1
    assert len(later_rows) == 2
    assert all(row.available_at <= APRIL_DECISION for row in early_rows)


def test_fixture_adapter_repeated_calls_are_deterministic():
    adapter = FixtureCapexInputAdapter()

    first = adapter.fetch_series("ai.token_proxy.growth", as_of=JULY_DECISION)
    second = adapter.fetch_series("ai.token_proxy.growth", as_of=JULY_DECISION)

    assert first == second
    assert tuple(row.value for row in first) == tuple(row.value for row in second)


def test_unknown_series_and_missing_as_of_return_empty_results():
    adapter = FixtureCapexInputAdapter()

    assert adapter.fetch_series("unknown.series", as_of=JULY_DECISION) == ()
    assert adapter.fetch_series("ai.capex.yoy") == ()


def test_fixture_adapter_exposes_bio_component_inputs():
    adapter = FixtureCapexInputAdapter()

    series_ids = adapter.list_series()

    assert "bio.capex.component.capacity_growth" in series_ids
    assert "bio.capex.component.backlog_growth" in series_ids
    assert adapter.fetch_series("bio.capex.component.capacity_growth", as_of=JULY_DECISION)


def test_company_metric_fixture_adapter_supports_pit_metrics():
    adapter = FixtureCompanyMetricAdapter()

    rows = adapter.fetch_metric("sample_bio_supplier", "order_backlog_growth", as_of=APRIL_DECISION)

    assert isinstance(adapter, CompanyMetricAdapter)
    assert adapter.list_metrics("sample_bio_supplier") == ("order_backlog_growth", "segment_revenue_growth")
    assert len(rows) == 1
    assert rows[0].series_id == "sample_bio_supplier:order_backlog_growth"
    assert rows[0].available_at <= APRIL_DECISION


def test_fixture_adapter_does_not_use_network_or_secrets():
    from api.data.adapters import fixtures

    source = fixtures.__loader__.get_source(fixtures.__name__)  # type: ignore[union-attr]

    assert "requests" not in source
    assert "httpx" not in source
    assert "urllib" not in source
    assert "socket" not in source
    assert "os.environ" not in source
    assert "dotenv" not in source
    assert "api.brokers" not in source
    assert "kis" not in source.lower()
