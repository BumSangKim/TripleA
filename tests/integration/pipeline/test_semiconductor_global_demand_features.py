from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorDataQuality, SemiconductorObservation
from api.score_pipeline.semiconductor_demand_features import (
    SemiconductorDemandFeatureMaterializer,
    load_semiconductor_demand_feature_definitions,
)


ROOT = Path(__file__).resolve().parents[3]


def test_released_fixture_rows_materialize_to_global_demand_feature_snapshot() -> None:
    rows = json.loads((ROOT / "tests" / "fixtures" / "semiconductor" / "global_demand_observations.json").read_text())
    decision_time = datetime(2025, 6, 30, tzinfo=UTC)
    observations = []
    for item in rows:
        for index, value in enumerate(item["values"], start=1):
            observations.append(
                SemiconductorObservation(
                    canonical_series_id=item["canonical_series_id"],
                    value=Decimal(value),
                    observation_date=datetime(2024 + ((index - 1) // 12), ((index - 1) % 12) + 1, 1).date(),
                    released_at=datetime(2025, 6, 1, tzinfo=UTC),
                    available_at=datetime(2025, 6, 1, tzinfo=UTC),
                    updated_at=datetime(2025, 6, 1, tzinfo=UTC),
                    source="fixture",
                    revision_id=f"v{index}",
                    vintage=f"v{index}",
                    frequency="monthly",
                    unit="index",
                    quality=SemiconductorDataQuality(1.0, False, False),
                )
            )
    repository = FixtureSemiconductorObservationRepository(observations)
    definitions = load_semiconductor_demand_feature_definitions(ROOT / "config" / "parameters" / "semiconductor_demand_features.yaml")

    snapshot = SemiconductorDemandFeatureMaterializer(definitions).materialize(repository, snapshot_id="global-demand-fixture", decision_time=decision_time)

    assert len(snapshot.features) == 7
    assert snapshot.by_id("semiconductor.demand.monthly_sales_yoy").feature_value is not None
    assert snapshot.by_id("semiconductor.demand.product_category_breadth").data_quality < 1.0
    assert "semiconductor.sales.product.category_b.monthly" in snapshot.missing_series_ids
