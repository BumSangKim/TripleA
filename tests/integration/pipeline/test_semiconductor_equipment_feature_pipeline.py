from __future__ import annotations
from datetime import UTC,datetime
from tests.unit.score_pipeline.test_semiconductor_equipment_features import ROOT,_repo
from api.score_pipeline.semiconductor_equipment_features import EquipmentCapacityFeatureMaterializer,load_equipment_feature_definitions
def test_equipment_fixture_materializes_distinct_demand_and_oversupply_inputs():
 d=load_equipment_feature_definitions(ROOT/"config/parameters/semiconductor_equipment_capacity_features.yaml");out=EquipmentCapacityFeatureMaterializer(d).materialize(_repo(d),snapshot_id="fixture",decision_time=datetime(2025,12,31,tzinfo=UTC));ids={x.feature_id for x in out};assert "semiconductor.equipment.bookings" in ids;assert "semiconductor.equipment.oversupply_risk_input" in ids
