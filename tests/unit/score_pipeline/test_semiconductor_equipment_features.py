from __future__ import annotations
from datetime import UTC,datetime
from decimal import Decimal
from pathlib import Path
from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorDataQuality,SemiconductorObservation
from api.score_pipeline.semiconductor_equipment_features import EquipmentCapacityFeatureMaterializer,load_equipment_feature_definitions
ROOT=Path(__file__).resolve().parents[3]
def test_equipment_features_keep_capex_fact_neutral_across_subsectors():
 d=load_equipment_feature_definitions(ROOT/"config/parameters/semiconductor_equipment_capacity_features.yaml"); out=EquipmentCapacityFeatureMaterializer(d).materialize(_repo(d),snapshot_id="fixture",decision_time=datetime(2025,12,31,tzinfo=UTC)); capex=next(x for x in out if x.feature_id.endswith("customer_capex")); assert capex.metadata["applicable_subsectors"]==["advanced_packaging","foundry","semiconductor_equipment"]; assert capex.metadata["interpretation"]=="deferred_to_subsector_scoring"; assert all("score" not in x.feature_id for x in out)
def _repo(d):
 rows=[]
 for series in d.series.values():
  for i in range(5):
   at=datetime(2025,12,1,tzinfo=UTC);rows.append(SemiconductorObservation(series,Decimal(100+i),datetime(2024+i//4,i%4*3+1,1).date(),at,at,at,"fixture",str(i),str(i),"quarterly","index",SemiconductorDataQuality(1,False,False)))
 return FixtureSemiconductorObservationRepository(rows)
