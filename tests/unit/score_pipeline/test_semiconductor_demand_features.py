from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorDataQuality, SemiconductorObservation
from api.score_pipeline.semiconductor_demand_features import (
    SemiconductorDemandFeatureMaterializer,
    load_semiconductor_demand_feature_definitions,
)


CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "parameters" / "semiconductor_demand_features.yaml"


def test_global_demand_feature_formulas_and_units_are_deterministic() -> None:
    materializer = SemiconductorDemandFeatureMaterializer(load_semiconductor_demand_feature_definitions(CONFIG_PATH))
    snapshot = materializer.materialize(_repository(global_values=list(range(100, 115))), snapshot_id="fixture", decision_time=_time())

    monthly_yoy = snapshot.by_id("semiconductor.demand.monthly_sales_yoy")
    average_yoy = snapshot.by_id("semiconductor.demand.three_month_average_yoy")
    momentum = snapshot.by_id("semiconductor.demand.three_month_annualized_momentum")

    assert monthly_yoy.feature_value == pytest.approx((114 / 102) - 1)
    assert average_yoy.feature_value == pytest.approx(((112 + 113 + 114) / 3) / ((100 + 101 + 102) / 3) - 1)
    assert momentum.feature_value == pytest.approx((1 + ((114 / 111) - 1)) ** 4 - 1)
    assert monthly_yoy.unit == "ratio"
    assert monthly_yoy.metadata["model_version"] == "semiconductor_demand_feature_model_v1"


def test_missing_configured_categories_reduce_quality_without_zero_filling() -> None:
    materializer = SemiconductorDemandFeatureMaterializer(load_semiconductor_demand_feature_definitions(CONFIG_PATH))
    snapshot = materializer.materialize(_repository(global_values=list(range(100, 115)), include_category_b=False), snapshot_id="fixture", decision_time=_time())

    product_breadth = snapshot.by_id("semiconductor.demand.product_category_breadth")
    assert product_breadth.feature_value == pytest.approx(1.0)
    assert snapshot.confidence < 1.0
    assert "semiconductor.sales.product.category_b.monthly" in snapshot.missing_series_ids


def _repository(*, global_values: list[int], include_category_b: bool = True) -> FixtureSemiconductorObservationRepository:
    series = {
        "semiconductor.sales.global.monthly": global_values,
        "semiconductor.sales.regional.region_a.monthly": global_values,
        "semiconductor.sales.regional.region_b.monthly": list(reversed(global_values)),
        "semiconductor.sales.product.category_a.monthly": global_values,
    }
    if include_category_b:
        series["semiconductor.sales.product.category_b.monthly"] = global_values
    observations = []
    for series_id, values in series.items():
        for month, value in enumerate(values, start=1):
            observations.append(
                SemiconductorObservation(
                    canonical_series_id=series_id,
                    value=Decimal(value),
                    observation_date=datetime(2024 + ((month - 1) // 12), ((month - 1) % 12) + 1, 1).date(),
                    released_at=datetime(2025, 6, 1, tzinfo=UTC),
                    available_at=datetime(2025, 6, 1, tzinfo=UTC),
                    updated_at=datetime(2025, 6, 1, tzinfo=UTC),
                    source="fixture",
                    revision_id=f"v{month}",
                    vintage=f"v{month}",
                    frequency="monthly",
                    unit="index",
                    quality=SemiconductorDataQuality(1.0, False, False),
                )
            )
    return FixtureSemiconductorObservationRepository(observations)


def _time() -> datetime:
    return datetime(2025, 6, 30, tzinfo=UTC)
