from __future__ import annotations

from api.features.strategy.models import StrategyMetadata
from api.features.strategy.ports import IStrategyRepository


def test_strategy_metadata_model():
    m = StrategyMetadata(universes={}, profiles={}, sector_taxonomy=None)
    assert m.universes == {}


def test_istrategy_repository_importable():
    assert IStrategyRepository is not None
