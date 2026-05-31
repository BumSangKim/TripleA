from __future__ import annotations

import inspect
from datetime import UTC, date, datetime

from api.data.capex_models import DataQualityIssueRecord, RawCompanyMetricPoint, RawTimeSeriesPoint, SourceFetchLogRecord
from api.data.capex_ports import CapexCompanyMetricSourceClient, CapexRawDataRepository, CapexTimeSeriesSourceClient


NOW = datetime(2026, 5, 31, 9, 0, tzinfo=UTC)


def test_fake_repository_conforms_to_raw_data_protocol():
    repo = FakeRepository()
    point = _time_series_point()
    metric = _company_metric_point()

    assert isinstance(repo, CapexRawDataRepository)
    assert repo.upsert_time_series([point]) == 1
    assert repo.upsert_company_metrics([metric]) == 1
    assert repo.read_time_series(metric_id="ai.capex.yoy")[0] == point
    assert repo.read_company_metrics(company_id="sample", metric_id="company.segment.growth")[0] == metric


def test_fake_source_clients_conform_to_protocols():
    time_series_client = FakeTimeSeriesClient()
    company_client = FakeCompanyMetricClient()

    assert isinstance(time_series_client, CapexTimeSeriesSourceClient)
    assert isinstance(company_client, CapexCompanyMetricSourceClient)
    assert time_series_client.fetch_time_series(metric_id="ai.capex.yoy", start=date(2026, 1, 1), end=date(2026, 5, 31))
    assert company_client.fetch_company_metrics(company_ids=["sample"], metric_ids=["company.segment.growth"])


def test_repository_methods_are_raw_data_only():
    method_names = [
        name
        for name, value in inspect.getmembers(CapexRawDataRepository)
        if inspect.isfunction(value) and not name.startswith("_")
    ]
    forbidden_terms = ("order", "execution", "broker", "kis", "submit", "trade")

    assert method_names
    assert all(name.startswith(("upsert_", "record_", "read_", "list_")) for name in method_names)
    assert not any(any(term in name.lower() for term in forbidden_terms) for name in method_names)


def test_ports_do_not_import_db_network_or_execution_layers():
    from api.data import capex_ports

    source = capex_ports.__loader__.get_source(capex_ports.__name__)  # type: ignore[union-attr]

    forbidden = ["sqlite3", "requests", "httpx", "urllib", "api.brokers", "api.features.orders", "api.strategy", "kis"]
    assert not [item for item in forbidden if item in source.lower()]


class FakeRepository:
    def __init__(self):
        self.time_series = []
        self.company_metrics = []
        self.fetch_logs = []
        self.quality_issues = []

    def upsert_time_series(self, points):
        self.time_series.extend(points)
        return len(points)

    def upsert_company_metrics(self, points):
        self.company_metrics.extend(points)
        return len(points)

    def record_fetch_log(self, record):
        self.fetch_logs.append(record)

    def record_quality_issue(self, record):
        self.quality_issues.append(record)

    def read_time_series(self, *, metric_id, source_id=None, start=None, end=None, as_of=None):
        return [point for point in self.time_series if point.metric_id == metric_id]

    def read_company_metrics(self, *, company_id, metric_id, source_id=None, period_start=None, period_end=None, as_of=None):
        return [point for point in self.company_metrics if point.company_id == company_id and point.metric_id == metric_id]

    def list_fetch_logs(self, *, source_id=None, limit=100):
        return self.fetch_logs[:limit]

    def list_quality_issues(self, *, metric_id=None, source_id=None, as_of_date=None, limit=100):
        return self.quality_issues[:limit]


class FakeTimeSeriesClient:
    client_name = "fixture"
    source_id = "fixture_time_series"

    def list_metrics(self):
        return ("ai.capex.yoy",)

    def fetch_time_series(self, *, metric_id, start, end, as_of=None):
        return [_time_series_point(metric_id=metric_id)]


class FakeCompanyMetricClient:
    client_name = "fixture"
    source_id = "fixture_company_metrics"

    def list_metrics(self):
        return ("company.segment.growth",)

    def fetch_company_metrics(self, *, company_ids, metric_ids, start_period=None, end_period=None, as_of=None):
        return [_company_metric_point(company_id=company_ids[0], metric_id=metric_ids[0])]


def _time_series_point(metric_id="ai.capex.yoy"):
    return RawTimeSeriesPoint(
        source="fixture",
        source_id="fixture_time_series",
        metric_id=metric_id,
        observation_date=date(2026, 3, 31),
        value="0.18",
        unit="year_over_year_change",
        available_at=NOW,
        updated_at=NOW,
    )


def _company_metric_point(company_id="sample", metric_id="company.segment.growth"):
    return RawCompanyMetricPoint(
        source="fixture",
        source_id="fixture_company_metrics",
        company_id=company_id,
        metric_id=metric_id,
        period="2026Q1",
        value="0.12",
        unit="year_over_year_change",
        available_at=NOW,
        updated_at=NOW,
    )


def _fetch_log():
    return SourceFetchLogRecord("fetch-1", "fixture", NOW, NOW, "success", 1)


def _quality_issue():
    return DataQualityIssueRecord(
        issue_id="issue-1",
        source_id="fixture",
        metric_id="ai.capex.yoy",
        severity="WARNING",
        reason_code="MISSING_DATA",
        message="missing data",
        as_of_date=date(2026, 5, 31),
        available_at=NOW,
        updated_at=NOW,
    )
