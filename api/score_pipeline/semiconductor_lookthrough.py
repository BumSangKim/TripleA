from __future__ import annotations
from dataclasses import dataclass
from datetime import date,datetime
from api.score_pipeline.contracts import ConservativeAction
@dataclass(frozen=True)
class ConstituentWeight: wrapper_id:str;company_id:str;weight:float;effective_date:date;available_at:datetime;is_semiconductor:bool
@dataclass(frozen=True)
class LookThroughExposure: company_exposure:dict[str,float];semiconductor_exposure:float;benchmark_semiconductor_exposure:float|None;active_tilt:float|None;confidence:float;reason_codes:tuple[str,...];fallback_state:str|None
def calculate_lookthrough(*,positions:dict[str,float],constituents:tuple[ConstituentWeight,...],decision_time:datetime,benchmark_id:str)->LookThroughExposure:
 eligible=[x for x in constituents if x.available_at<=decision_time and x.effective_date<=decision_time.date()];by={}
 for x in eligible:by.setdefault(x.wrapper_id,[]).append(x)
 exposure={};missing=[]
 for wrapper,weight in positions.items():
  rows=by.get(wrapper,[])
  if not rows:missing.append(wrapper);continue
  for x in rows:exposure[x.company_id]=exposure.get(x.company_id,0)+weight*x.weight
 semi=sum(weight for company,weight in exposure.items() if any(x.company_id==company and x.is_semiconductor for x in eligible));bench=sum(x.weight for x in by.get(benchmark_id,[]) if x.is_semiconductor) if by.get(benchmark_id) else None
 return LookThroughExposure(exposure,semi,bench,None if bench is None else semi-bench,1-len(missing)/max(len(positions),1),("LOOKTHROUGH_BENCHMARK_UNAVAILABLE",) if bench is None else ("LOOKTHROUGH_CALCULATED",),ConservativeAction.REVIEW_REQUIRED if bench is None else None)
