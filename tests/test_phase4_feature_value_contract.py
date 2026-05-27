from dataclasses import fields
from datetime import UTC, date, datetime

import pytest

from api.plugin_boundary.contracts import FeatureValue, PluginBoundaryContractError


NOW = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)


def _feature(**overrides):
    data = {
        "feature_id": "market.price_momentum_3m",
        "entity_type": "asset",
        "entity_id": "KRX_360750",
        "feature_value": 0.12,
        "unit": "ratio",
        "as_of_date": date(2026, 5, 27),
        "available_at": NOW,
        "source_dataset_ids": ["ds-1"],
        "source_plugin_ids": ["mock_price_plugin"],
        "calculation_method": "standard_dataset_price_return",
        "feature_version": "feature_value_v1",
        "parameter_version": None,
        "data_quality": 0.9,
        "missing_ratio": 0.0,
        "is_stale": False,
    }
    data.update(overrides)
    return FeatureValue(**data)


def test_valid_feature_value_can_be_created():
    feature = _feature(metadata={"window": "3m"})

    assert feature.feature_id == "market.price_momentum_3m"
    assert feature.feature_value == 0.12
    assert feature.source_dataset_ids == ["ds-1"]
    assert feature.source_plugin_ids == ["mock_price_plugin"]
    assert feature.metadata == {"window": "3m"}


def test_feature_id_is_required():
    with pytest.raises(PluginBoundaryContractError, match="feature_id"):
        _feature(feature_id="")


def test_available_at_is_required():
    with pytest.raises(PluginBoundaryContractError, match="available_at"):
        _feature(available_at=None)


def test_data_quality_range_is_validated():
    with pytest.raises(PluginBoundaryContractError, match="data_quality"):
        _feature(data_quality=1.2)


def test_missing_ratio_range_is_validated():
    with pytest.raises(PluginBoundaryContractError, match="missing_ratio"):
        _feature(missing_ratio=-0.1)


def test_source_dataset_ids_are_required_for_traceability():
    with pytest.raises(PluginBoundaryContractError, match="source_dataset_ids"):
        _feature(source_dataset_ids=[])


def test_feature_value_has_no_score_or_action_fields():
    field_names = {field.name for field in fields(FeatureValue)}

    blocked = {"score", "action", "buy", "sell", "weight", "allocation", "rebalance", "order"}
    assert not blocked.intersection(field_names)


def test_feature_id_rejects_score_or_action_namespace():
    with pytest.raises(PluginBoundaryContractError, match="score/action"):
        _feature(feature_id="market.momentum_score")

    with pytest.raises(PluginBoundaryContractError, match="score/action"):
        _feature(feature_id="market.buy_signal")
