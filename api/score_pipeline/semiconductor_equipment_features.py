from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import yaml
from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorObservation
from api.plugin_boundary.contracts import FeatureValue

@dataclass(frozen=True)
class EquipmentFeatureDefinitions:
    parameter_version: str; model_version: str; applicability: dict[str, tuple[str,...]]; series: dict[str,str]
def load_equipment_feature_definitions(path: str|Path)->EquipmentFeatureDefinitions:
    raw=yaml.safe_load(Path(path).read_text()) or {}; meta=raw["parameter_metadata"]
    return EquipmentFeatureDefinitions(str(meta["parameter_version"]),str(meta["model_version"]),{k:tuple(v) for k,v in raw["subsector_applicability"].items()},{k:str(v) for k,v in raw["series"].items()})
class EquipmentCapacityFeatureMaterializer:
    def __init__(self, definitions:EquipmentFeatureDefinitions)->None:self._d=definitions
    def materialize(self,repository:FixtureSemiconductorObservationRepository,*,snapshot_id:str,decision_time:datetime)->tuple[FeatureValue,...]:
        output=[]
        for metric,series_id in self._d.series.items():
            rows=repository.select_available_series(series_id,decision_time=decision_time); values=[float(r.value) for r in rows if r.value is not None]
            value=None if not values else (values[-1]/values[-5]-1 if len(values)>=5 and values[-5] else values[-1])
            applicable=sorted(subsector for subsector,metrics in self._d.applicability.items() if metric in metrics)
            at=max((r.available_at for r in rows),default=datetime.min)
            feature_metric = "bookings" if metric == "orders" else metric
            output.append(FeatureValue(f"semiconductor.equipment.{feature_metric}","universe","SEMICONDUCTOR_ACTIVE_OVERLAY",value,"ratio",at.date(),at,[snapshot_id],[],feature_metric,"semiconductor_equipment_capacity_features_v1",self._d.parameter_version,1.0 if value is not None else 0.0,0.0 if value is not None else 1.0,any(r.quality.stale for r in rows),["EQUIPMENT_FEATURE_UNAVAILABLE"] if value is None else [],["EQUIPMENT_CAPACITY_FACT_ONLY"],{"model_version":self._d.model_version,"source_metric":metric,"applicable_subsectors":applicable,"interpretation":"deferred_to_subsector_scoring"}))
        return tuple(output)
