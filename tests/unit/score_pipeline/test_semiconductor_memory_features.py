from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorDataQuality, SemiconductorObservation
from api.score_pipeline.normalization_primitives import load_normalization_parameters
from api.score_pipeline.semiconductor_memory_features import MemoryPriceFeatureMaterializer, load_memory_price_feature_definitions


ROOT = Path(__file__).resolve().parents[3]


def test_memory_features_distinguish_spot_contract_and_keep_missing_hbm_optional() -> None:
    materializer = MemoryPriceFeatureMaterializer(load_memory_price_feature_definitions(ROOT / "config/parameters/semiconductor_memory_price_features.yaml"), load_normalization_parameters(ROOT / "config/parameters/semiconductor_normalization.yaml"))
    snapshot = materializer.materialize(_repository(), snapshot_id="fixture", decision_time=datetime(2025, 12, 31, tzinfo=UTC))

    ids = {feature.feature_id for feature in snapshot.features}
    assert "semiconductor.memory.dram.spot.momentum_3m" in ids
    assert "semiconductor.memory.dram.contract.momentum_3m" in ids
    assert "semiconductor.memory.dram.spot_contract_spread" in ids
    assert "semiconductor.memory.hbm.contract.monthly" in snapshot.missing_optional_series
    assert snapshot.confidence < 1.0
    assert all("order" not in feature.feature_id for feature in snapshot.features)


def _repository() -> FixtureSemiconductorObservationRepository:
    observations = []
    for series_id, base in (("semiconductor.memory.dram.spot.monthly", 100), ("semiconductor.memory.dram.contract.monthly", 90), ("semiconductor.memory.nand.spot.monthly", 80), ("semiconductor.memory.nand.contract.monthly", 75), ("semiconductor.memory.server.contract.monthly", 110)):
        for month in range(18):
            observations.append(SemiconductorObservation(series_id, Decimal(base + month), datetime(2024 + month // 12, month % 12 + 1, 1).date(), datetime(2025, 12, 1, tzinfo=UTC), datetime(2025, 12, 1, tzinfo=UTC), datetime(2025, 12, 1, tzinfo=UTC), "fixture", f"v{month}", f"v{month}", "monthly", "index", SemiconductorDataQuality(1.0, False, False)))
    return FixtureSemiconductorObservationRepository(observations)
