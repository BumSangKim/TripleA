from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorDataQuality, SemiconductorObservation
from api.score_pipeline.semiconductor_inventory_supply_features import InventorySupplyFeatureMaterializer, load_inventory_supply_definitions

ROOT = Path(__file__).resolve().parents[3]

def test_inventory_pressure_direction_and_future_filing_exclusion() -> None:
    decision = datetime(2025, 12, 31, tzinfo=UTC)
    snapshot = InventorySupplyFeatureMaterializer(load_inventory_supply_definitions(ROOT / "config/parameters/semiconductor_inventory_supply_features.yaml")).materialize(_repo(future=True), snapshot_id="fixture", decision_time=decision)
    assert snapshot.features
    pressure = next(feature for feature in snapshot.features if feature.feature_id.endswith("inventory_growth_minus_revenue_growth"))
    assert float(pressure.feature_value) > 0
    assert len(_repo(future=True).select_available_series("semiconductor.company.company_b.capex.quarterly", decision_time=decision)) == 4

def test_missing_company_inputs_produce_conservative_feature_values() -> None:
    snapshot = InventorySupplyFeatureMaterializer(load_inventory_supply_definitions(ROOT / "config/parameters/semiconductor_inventory_supply_features.yaml")).materialize(FixtureSemiconductorObservationRepository(()), snapshot_id="fixture", decision_time=datetime(2025, 12, 31, tzinfo=UTC))
    assert snapshot.coverage == 0.0
    assert all(feature.feature_value is None for feature in snapshot.features)

def _repo(*, future: bool) -> FixtureSemiconductorObservationRepository:
    obs=[]
    metrics={"inventory_days":[10,11,12,13,18],"revenue":[100,105,110,115,140],"utilization":[70,72,74,75,76],"capacity":[100,102,104,106,110],"bit_growth":[100,101,103,106,110],"capex":[100,102,104,106,110]}
    for company in ("company_a","company_b"):
        for metric,values in metrics.items(): obs.extend(_rows(f"semiconductor.company.{company}.{metric}.quarterly",values, future=future and company=="company_b" and metric=="capex"))
    obs.extend(_rows("semiconductor.end_demand.global.quarterly",[100,102,104,106,108],future=False))
    return FixtureSemiconductorObservationRepository(obs)

def _rows(series_id, values, *, future):
    result=[]
    for index,value in enumerate(values):
        available=datetime(2026,1,1,tzinfo=UTC) if future and index==len(values)-1 else datetime(2025,12,1,tzinfo=UTC)
        result.append(SemiconductorObservation(series_id,Decimal(value),datetime(2024+index//4,index%4*3+1,1).date(),available,available,available,"fixture",f"v{index}",f"v{index}","quarterly","index",SemiconductorDataQuality(1,False,False)))
    return result
