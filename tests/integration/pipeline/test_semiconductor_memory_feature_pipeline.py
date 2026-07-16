from __future__ import annotations

from tests.unit.score_pipeline.test_semiconductor_memory_features import ROOT, _repository
from api.score_pipeline.normalization_primitives import load_normalization_parameters
from api.score_pipeline.semiconductor_memory_features import MemoryPriceFeatureMaterializer, load_memory_price_feature_definitions


def test_memory_fixture_reaches_feature_snapshot_without_action_surface() -> None:
    snapshot = MemoryPriceFeatureMaterializer(load_memory_price_feature_definitions(ROOT / "config/parameters/semiconductor_memory_price_features.yaml"), load_normalization_parameters(ROOT / "config/parameters/semiconductor_normalization.yaml")).materialize(_repository(), snapshot_id="memory-fixture", decision_time=__import__("datetime").datetime(2025, 12, 31, tzinfo=__import__("datetime").UTC))
    assert snapshot.features
    assert all(feature.feature_value is None or -1.0 <= float(feature.feature_value) <= 1.0 or feature.unit in {"ratio", "fraction"} for feature in snapshot.features)
