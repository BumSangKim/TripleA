from datetime import UTC, date, datetime

import pytest

from api.plugin_boundary.contracts import PluginBoundaryContractError, PluginDataset


def _dataset(**overrides):
    data = {
        "dataset_id": "ds-1",
        "dataset_type": "market_price_daily",
        "plugin_id": "mock_price_plugin",
        "provider": "mock",
        "source": "mock_krx_daily_prices",
        "entity_type": "asset",
        "entity_id": "KRX_360750",
        "data": [{"close": "100.0"}],
        "schema_version": "plugin_dataset_v1",
        "as_of_date": date(2026, 5, 27),
        "available_at": datetime(2026, 5, 27, 9, 5, tzinfo=UTC),
        "retrieved_at": datetime(2026, 5, 27, 9, 6, tzinfo=UTC),
        "quality_score": 0.95,
        "missing_ratio": 0.0,
        "is_stale": False,
    }
    data.update(overrides)
    return PluginDataset(**data)


def test_valid_plugin_dataset_can_be_created():
    dataset = _dataset(metadata={"unit": "KRW"})

    assert dataset.dataset_type == "market_price_daily"
    assert dataset.plugin_id == "mock_price_plugin"
    assert dataset.metadata == {"unit": "KRW"}
    assert dataset.warnings == []
    assert dataset.reason_codes == []


def test_dataset_type_is_required():
    with pytest.raises(PluginBoundaryContractError, match="dataset_type"):
        _dataset(dataset_type="")


def test_available_at_is_required():
    with pytest.raises(PluginBoundaryContractError, match="available_at"):
        _dataset(available_at=None)


def test_retrieved_at_is_required():
    with pytest.raises(PluginBoundaryContractError, match="retrieved_at"):
        _dataset(retrieved_at=None)


def test_quality_score_range_is_validated():
    with pytest.raises(PluginBoundaryContractError, match="quality_score"):
        _dataset(quality_score=1.1)


def test_missing_ratio_range_is_validated():
    with pytest.raises(PluginBoundaryContractError, match="missing_ratio"):
        _dataset(missing_ratio=-0.1)


def test_plugin_id_cannot_stand_in_for_dataset_type():
    with pytest.raises(PluginBoundaryContractError, match="plugin_id"):
        _dataset(dataset_type="mock_price_plugin", plugin_id="mock_price_plugin")
