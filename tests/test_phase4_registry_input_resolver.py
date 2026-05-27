from datetime import UTC, date, datetime, timedelta

import inspect
import pytest

from api.plugin_boundary.contracts import PluginBoundaryContractError, PluginDataset, PluginHealthStatus
from api.plugin_boundary.input_resolver import FeatureInputResolver, FeatureSpec
import api.plugin_boundary.input_resolver as resolver_module
from api.plugin_boundary.registry import PluginRegistration, PluginRegistry


NOW = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)


def _dataset(plugin_id, dataset_id, *, available_at=NOW, quality_score=0.9):
    return PluginDataset(
        dataset_id=dataset_id,
        dataset_type="market_price_daily",
        plugin_id=plugin_id,
        provider="mock",
        source="mock_source",
        entity_type="asset",
        entity_id="KRX_360750",
        data=[{"close": "100"}],
        schema_version="plugin_dataset_v1",
        as_of_date=date(2026, 5, 27),
        available_at=available_at,
        retrieved_at=available_at,
        quality_score=quality_score,
        missing_ratio=0.0,
        is_stale=False,
    )


def _registry():
    registry = PluginRegistry()
    registry.register(PluginRegistration("slow_plugin", "mock", ("market_price_daily",), priority=20))
    registry.register(PluginRegistration("fast_plugin", "mock", ("market_price_daily",), priority=10))
    return registry


def _spec():
    return FeatureSpec(
        feature_id="market.price_momentum_3m",
        mode="reusable_calculator",
        entity_type="asset",
        calculator="market_price_momentum",
        required_dataset_types=("market_price_daily",),
    )


def test_registry_returns_plugin_candidates_by_dataset_type_in_priority_order():
    candidates = _registry().candidates_for_dataset_type("market_price_daily")

    assert [plugin.plugin_id for plugin in candidates] == ["fast_plugin", "slow_plugin"]


def test_resolver_applies_plugin_priority():
    datasets = [_dataset("slow_plugin", "slow"), _dataset("fast_plugin", "fast")]

    result = FeatureInputResolver(_registry(), datasets).resolve(
        _spec(),
        entity_id="KRX_360750",
        decision_time=NOW,
    )

    assert result.datasets_by_type["market_price_daily"].dataset_id == "fast"
    assert result.fallback_used is False


def test_resolver_excludes_failed_plugins():
    registry = PluginRegistry()
    failed_health = PluginHealthStatus(
        plugin_id="fast_plugin",
        status="FAILED",
        last_success_at=None,
        last_failure_at=NOW,
        error_code="PLUGIN_PROVIDER_ERROR",
        error_message="failed",
        latency_ms=None,
        checked_at=NOW,
    )
    registry.register(PluginRegistration("fast_plugin", "mock", ("market_price_daily",), priority=10, health=failed_health))
    registry.register(PluginRegistration("slow_plugin", "mock", ("market_price_daily",), priority=20))
    datasets = [_dataset("fast_plugin", "fast"), _dataset("slow_plugin", "slow")]

    result = FeatureInputResolver(registry, datasets).resolve(_spec(), entity_id="KRX_360750", decision_time=NOW)

    assert result.datasets_by_type["market_price_daily"].dataset_id == "slow"


def test_resolver_returns_fallback_reason_when_dataset_missing():
    result = FeatureInputResolver(_registry(), []).resolve(_spec(), entity_id="KRX_360750", decision_time=NOW)

    assert result.fallback_used is True
    assert result.reason_codes == ["PLUGIN_DATASET_FALLBACK_USED"]
    assert result.warnings == ["PLUGIN_DATASET_UNAVAILABLE:market_price_daily"]


def test_resolver_excludes_datasets_after_decision_time():
    datasets = [_dataset("fast_plugin", "future", available_at=NOW + timedelta(minutes=1))]

    result = FeatureInputResolver(_registry(), datasets).resolve(_spec(), entity_id="KRX_360750", decision_time=NOW)

    assert result.datasets_by_type == {}
    assert result.fallback_used is True


def test_reusable_feature_spec_rejects_required_plugins():
    with pytest.raises(PluginBoundaryContractError, match="required_plugins"):
        FeatureSpec(
            feature_id="market.price_momentum_3m",
            mode="reusable_calculator",
            entity_type="asset",
            calculator="market_price_momentum",
            required_dataset_types=("market_price_daily",),
            required_plugins=("fast_plugin",),
        )


def test_input_resolver_does_not_import_concrete_plugin_classes():
    source = inspect.getsource(resolver_module)

    assert "api.data.plugins" not in source
    assert "api.strategy.indicator_plugins" not in source
