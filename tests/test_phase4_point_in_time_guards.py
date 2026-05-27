import sqlite3
from datetime import UTC, date, datetime

import pytest

from api.plugin_boundary.contracts import FeatureValue, PluginBoundaryContractError, PluginDataset, PluginSignal
from api.plugin_boundary.storage import read_feature_values, read_plugin_signals, save_feature_value, save_plugin_signal
from api.plugin_boundary.time_guard import filter_available_values, is_available_for_decision


DECISION_TIME = datetime(2026, 4, 15, 9, 0, tzinfo=UTC)


def _dataset(as_of_date, available_at, dataset_type="macro_series_monthly"):
    return PluginDataset(
        dataset_id=f"{dataset_type}:{as_of_date.isoformat()}",
        dataset_type=dataset_type,
        plugin_id="mock_plugin",
        provider="mock",
        source="mock_source",
        entity_type="macro",
        entity_id="CPI",
        data=[{"value": "2.1"}],
        schema_version="plugin_dataset_v1",
        as_of_date=as_of_date,
        available_at=available_at,
        retrieved_at=available_at,
        quality_score=0.9,
        missing_ratio=0.0,
        is_stale=False,
    )


def _feature(available_at):
    return FeatureValue(
        feature_id="macro.cpi_yoy",
        entity_type="macro",
        entity_id="CPI",
        feature_value=0.021,
        unit="ratio",
        as_of_date=date(2026, 3, 31),
        available_at=available_at,
        source_dataset_ids=["macro_series_monthly:2026-03-31"],
        source_plugin_ids=["mock_plugin"],
        calculation_method="released_macro_yoy",
        feature_version="v1",
        parameter_version=None,
        data_quality=0.9,
        missing_ratio=0.0,
        is_stale=False,
    )


def _signal(available_at):
    return PluginSignal(
        signal_id="plugin_signal:earnings_revision:COMPANY_X",
        plugin_id="earnings_plugin",
        provider="mock",
        source="earnings_provider",
        entity_type="company",
        entity_id="COMPANY_X",
        signal_value="positive_revision",
        signal_unit="category",
        signal_direction="risk_up",
        source_native=True,
        calculation_method="provider_revision_signal",
        plugin_version="v1",
        signal_version="v1",
        as_of_date=date(2026, 3, 31),
        available_at=available_at,
        retrieved_at=available_at,
        quality_score=0.8,
        source_dataset_ids=["earnings:COMPANY_X:2026Q1"],
        metadata={"usage_reason": "provider-native earnings revision timing"},
    )


def _conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "pit.db")
    conn.row_factory = sqlite3.Row
    return conn


def test_available_at_before_or_equal_decision_time_passes():
    dataset = _dataset(date(2026, 3, 31), DECISION_TIME)

    assert is_available_for_decision(dataset, DECISION_TIME) is True


def test_as_of_date_in_past_but_available_at_in_future_is_excluded():
    dataset = _dataset(date(2026, 3, 31), datetime(2026, 5, 10, 9, 0, tzinfo=UTC))

    assert is_available_for_decision(dataset, DECISION_TIME) is False
    assert filter_available_values([dataset], DECISION_TIME) == []


def test_missing_available_at_fails_conservatively():
    class MissingAvailableAt:
        pass

    with pytest.raises(PluginBoundaryContractError, match="available_at"):
        is_available_for_decision(MissingAvailableAt(), DECISION_TIME)


def test_plugin_signal_uses_same_point_in_time_guard():
    signal = _signal(datetime(2026, 5, 1, 9, 0, tzinfo=UTC))

    assert filter_available_values([signal], DECISION_TIME) == []


def test_feature_repository_filters_available_at(tmp_path):
    conn = _conn(tmp_path)
    save_feature_value(conn, _feature(DECISION_TIME))
    save_feature_value(conn, _feature(datetime(2026, 5, 10, 9, 0, tzinfo=UTC)))

    rows = read_feature_values(
        conn,
        feature_id="macro.cpi_yoy",
        entity_type="macro",
        entity_id="CPI",
        decision_time=DECISION_TIME,
    )

    assert len(rows) == 1
    assert rows[0].available_at == DECISION_TIME


def test_plugin_signal_repository_filters_available_at(tmp_path):
    conn = _conn(tmp_path)
    save_plugin_signal(conn, _signal(datetime(2026, 5, 10, 9, 0, tzinfo=UTC)))

    rows = read_plugin_signals(
        conn,
        signal_id="plugin_signal:earnings_revision:COMPANY_X",
        entity_type="company",
        entity_id="COMPANY_X",
        decision_time=DECISION_TIME,
    )

    assert rows == []


def test_monthly_macro_release_lag_case_is_excluded_before_release():
    monthly_macro = _dataset(date(2026, 3, 31), datetime(2026, 5, 10, 9, 0, tzinfo=UTC))

    assert monthly_macro.as_of_date < DECISION_TIME.date()
    assert is_available_for_decision(monthly_macro, DECISION_TIME) is False


def test_company_earnings_announcement_date_case_is_excluded_before_announcement():
    earnings_signal = _signal(datetime(2026, 4, 30, 9, 0, tzinfo=UTC))

    assert earnings_signal.as_of_date < DECISION_TIME.date()
    assert is_available_for_decision(earnings_signal, DECISION_TIME) is False


def test_etf_constituent_effective_date_case_uses_available_date():
    constituents = _dataset(
        date(2026, 4, 1),
        datetime(2026, 4, 20, 9, 0, tzinfo=UTC),
        dataset_type="etf_constituents_point_in_time",
    )

    assert constituents.as_of_date <= DECISION_TIME.date()
    assert is_available_for_decision(constituents, DECISION_TIME) is False
