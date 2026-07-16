from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import pstdev
import yaml
from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository
from api.domain.semiconductor_observations import SemiconductorObservation
from api.plugin_boundary.contracts import FeatureValue
@dataclass(frozen=True)
class EarningsDefinitions: parameter_version:str; model_version:str; companies:tuple[str,...]; metrics:tuple[str,...]
def load_earnings_definitions(path:str|Path)->EarningsDefinitions:
 raw=yaml.safe_load(Path(path).read_text()) or {};m=raw["parameter_metadata"];return EarningsDefinitions(str(m["parameter_version"]),str(m["model_version"]),tuple(raw["companies"]),tuple(raw["metrics"]))
class EarningsQualityFeatureMaterializer:
 def __init__(self,d:EarningsDefinitions)->None:self._d=d
 def materialize(self,r:FixtureSemiconductorObservationRepository,*,snapshot_id:str,decision_time:datetime)->tuple[FeatureValue,...]:
  out=[]; revisions=[]
  for company in self._d.companies:
   values={metric:_values(r.select_available_series(f"semiconductor.company.{company}.{metric}.monthly",decision_time=decision_time)) for metric in self._d.metrics}
   for metric,months in (("eps_estimate",1),("eps_estimate",3),("revenue_estimate",3)):
    value=_revision(values[metric],months);revisions.append(value) if metric=="eps_estimate" and months==1 and value is not None else None;out.append(self._f(company,f"{metric}_revision_{months}m",value,snapshot_id,values[metric],decision_time))
   for metric in ("margin","fcf_margin","roic") :out.append(self._f(company,f"{metric}_trend",_trend(values[metric]),snapshot_id,values[metric],decision_time))
   out.append(self._f(company,"balance_sheet_quality",values["balance_sheet_quality"][-1] if values["balance_sheet_quality"] else None,snapshot_id,values["balance_sheet_quality"],decision_time))
   out.append(self._f(company,"earnings_volatility_inverse",None if len(values["earnings"])<2 else 1/(1+pstdev(values["earnings"])),snapshot_id,values["earnings"],decision_time))
  breadth=None if not revisions else sum(x>0 for x in revisions)/len(revisions);out.append(self._f("SEMICONDUCTOR_ACTIVE_OVERLAY","positive_revision_breadth",breadth,snapshot_id,[],decision_time));return tuple(out)
 def _f(self,company,name,value,snapshot_id,values,decision_time):
  return FeatureValue(f"semiconductor.earnings.{name}","asset" if company!="SEMICONDUCTOR_ACTIVE_OVERLAY" else "universe",company,value,"ratio",decision_time.date(),decision_time,[snapshot_id],[],name,"semiconductor_earnings_quality_features_v1",self._d.parameter_version,1.0 if value is not None else 0.0,0.0 if value is not None else 1.0,False,["EARNINGS_ESTIMATE_UNAVAILABLE"] if value is None else [],["EARNINGS_QUALITY_REVIEW_REQUIRED"] if value is None else ["EARNINGS_FEATURE_MATERIALIZED"],{"model_version":self._d.model_version})
def _values(rows:tuple[SemiconductorObservation,...])->list[float]:return [float(x.value) for x in rows if x.value is not None]
def _revision(v:list[float],months:int)->float|None:return None if len(v)<=months or v[-1-months]==0 else v[-1]/v[-1-months]-1
def _trend(v:list[float])->float|None:return None if len(v)<2 else v[-1]-v[0]
