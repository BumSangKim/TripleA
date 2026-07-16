from __future__ import annotations
from datetime import UTC, datetime
from tests.unit.score_pipeline.test_semiconductor_inventory_supply_features import ROOT, _repo
from api.score_pipeline.semiconductor_inventory_supply_features import InventorySupplyFeatureMaterializer, load_inventory_supply_definitions

def test_inventory_supply_fixture_reaches_auditable_feature_output():
    snapshot=InventorySupplyFeatureMaterializer(load_inventory_supply_definitions(ROOT / "config/parameters/semiconductor_inventory_supply_features.yaml")).materialize(_repo(future=False),snapshot_id="fixture",decision_time=datetime(2025,12,31,tzinfo=UTC))
    assert len(snapshot.features)==10
    assert all("model_version" in feature.metadata for feature in snapshot.features)
