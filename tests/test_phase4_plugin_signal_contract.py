from datetime import UTC, date, datetime

import pytest

from api.plugin_boundary.contracts import PluginBoundaryContractError, PluginSignal


NOW = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)


def _signal(**overrides):
    data = {
        "signal_id": "plugin_signal:bottleneck_pressure:SEMICONDUCTOR",
        "plugin_id": "supply_chain_plugin",
        "provider": "mock",
        "source": "supply_chain_model",
        "entity_type": "sector",
        "entity_id": "SEMICONDUCTOR",
        "signal_value": "elevated",
        "signal_unit": "category",
        "signal_direction": "risk_up",
        "source_native": True,
        "calculation_method": "provider_native_signal",
        "plugin_version": "v1",
        "signal_version": "plugin_signal_v1",
        "as_of_date": date(2026, 5, 27),
        "available_at": NOW,
        "retrieved_at": NOW,
        "quality_score": 0.8,
        "source_dataset_ids": ["ds-1"],
        "reason_codes": ["PLUGIN_NATIVE_SIGNAL"],
        "warnings": [],
        "metadata": {"usage_reason": "source model defines bottleneck pressure semantics"},
    }
    data.update(overrides)
    return PluginSignal(**data)


def test_valid_plugin_signal_can_be_created():
    signal = _signal()

    assert signal.source_native is True
    assert signal.plugin_id == "supply_chain_plugin"
    assert signal.signal_value == "elevated"
    assert signal.metadata["usage_reason"]


def test_plugin_signal_requires_available_at():
    with pytest.raises(PluginBoundaryContractError, match="available_at"):
        _signal(available_at=None)


def test_plugin_signal_rejects_non_source_native_values():
    with pytest.raises(PluginBoundaryContractError, match="source_native"):
        _signal(source_native=False)


def test_plugin_signal_quality_score_range_is_validated():
    with pytest.raises(PluginBoundaryContractError, match="quality_score"):
        _signal(quality_score=1.5)


def test_plugin_signal_id_cannot_use_feature_namespace():
    with pytest.raises(PluginBoundaryContractError, match="feature namespace"):
        _signal(signal_id="feature:bottleneck_pressure")

    with pytest.raises(PluginBoundaryContractError, match="feature namespace"):
        _signal(signal_id="feature_bottleneck_pressure")


def test_plugin_signal_requires_usage_reason_metadata():
    with pytest.raises(PluginBoundaryContractError, match="usage_reason"):
        _signal(metadata={})
