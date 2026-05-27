import sqlite3
from datetime import UTC, date, datetime, timedelta

from api.plugin_boundary.contracts import FeatureValue, PluginSignal
from api.plugin_boundary.storage import (
    ensure_traceability_tables,
    read_feature_values,
    read_plugin_signals,
    save_feature_value,
    save_plugin_signal,
)


NOW = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)


def _conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "traceability.db")
    conn.row_factory = sqlite3.Row
    return conn


def _feature(feature_version="v1", available_at=NOW, value=0.12):
    return FeatureValue(
        feature_id="market.price_momentum_3m",
        entity_type="asset",
        entity_id="KRX_360750",
        feature_value=value,
        unit="ratio",
        as_of_date=date(2026, 5, 27),
        available_at=available_at,
        source_dataset_ids=["ds-1"],
        source_plugin_ids=["mock_price_plugin"],
        calculation_method="standard_dataset_price_return",
        feature_version=feature_version,
        parameter_version=None,
        data_quality=0.9,
        missing_ratio=0.0,
        is_stale=False,
        reason_codes=["FEATURE_VALUE_CREATED"],
    )


def _signal(available_at=NOW):
    return PluginSignal(
        signal_id="plugin_signal:news_sentiment:KRX_360750",
        plugin_id="news_sentiment_plugin",
        provider="mock",
        source="news_model",
        entity_type="asset",
        entity_id="KRX_360750",
        signal_value="positive",
        signal_unit="category",
        signal_direction="risk_up",
        source_native=True,
        calculation_method="provider_native_signal",
        plugin_version="plugin_v1",
        signal_version="signal_v1",
        as_of_date=date(2026, 5, 27),
        available_at=available_at,
        retrieved_at=available_at,
        quality_score=0.8,
        source_dataset_ids=["news-ds-1"],
        reason_codes=["PLUGIN_NATIVE_SIGNAL"],
        metadata={"usage_reason": "provider-native sentiment model"},
    )


def test_traceability_tables_can_be_created(tmp_path):
    conn = _conn(tmp_path)

    ensure_traceability_tables(conn)

    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"plugin_boundary_feature_values", "plugin_boundary_plugin_signals"}.issubset(tables)


def test_feature_value_can_be_saved_and_read_with_source_dataset_ids(tmp_path):
    conn = _conn(tmp_path)

    row_id = save_feature_value(conn, _feature())
    rows = read_feature_values(conn, feature_id="market.price_momentum_3m", entity_type="asset", entity_id="KRX_360750")

    assert row_id > 0
    assert rows[0].source_dataset_ids == ["ds-1"]
    assert rows[0].source_plugin_ids == ["mock_price_plugin"]


def test_feature_value_query_filters_by_available_at(tmp_path):
    conn = _conn(tmp_path)
    save_feature_value(conn, _feature(feature_version="v1", available_at=NOW, value=0.12))
    save_feature_value(conn, _feature(feature_version="v2", available_at=NOW + timedelta(days=1), value=0.20))

    rows = read_feature_values(
        conn,
        feature_id="market.price_momentum_3m",
        entity_type="asset",
        entity_id="KRX_360750",
        decision_time=NOW,
    )

    assert [row.feature_version for row in rows] == ["v1"]


def test_revised_feature_versions_are_not_overwritten(tmp_path):
    conn = _conn(tmp_path)
    save_feature_value(conn, _feature(feature_version="v1"))
    save_feature_value(conn, _feature(feature_version="v2"))

    rows = read_feature_values(conn, feature_id="market.price_momentum_3m", entity_type="asset", entity_id="KRX_360750")

    assert {row.feature_version for row in rows} == {"v1", "v2"}


def test_plugin_signal_can_be_saved_and_read(tmp_path):
    conn = _conn(tmp_path)

    save_plugin_signal(conn, _signal())
    rows = read_plugin_signals(
        conn,
        signal_id="plugin_signal:news_sentiment:KRX_360750",
        entity_type="asset",
        entity_id="KRX_360750",
    )

    assert rows[0].plugin_id == "news_sentiment_plugin"
    assert rows[0].source_native is True
    assert rows[0].source_dataset_ids == ["news-ds-1"]


def test_plugin_signal_query_filters_by_available_at(tmp_path):
    conn = _conn(tmp_path)
    save_plugin_signal(conn, _signal(available_at=NOW + timedelta(hours=1)))

    rows = read_plugin_signals(
        conn,
        signal_id="plugin_signal:news_sentiment:KRX_360750",
        entity_type="asset",
        entity_id="KRX_360750",
        decision_time=NOW,
    )

    assert rows == []
