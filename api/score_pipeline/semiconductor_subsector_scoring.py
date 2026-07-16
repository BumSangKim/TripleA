from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml
from api.score_pipeline.contracts import ConservativeAction,PipelineContractError
@dataclass(frozen=True)
class SubsectorScore: subsector:str;score:float;confidence:float;data_quality:float;parameter_version:str;model_version:str;fallback_state:str|None;reason_codes:tuple[str,...]
def load_candidate(path:str|Path)->dict:
 data=yaml.safe_load(Path(path).read_text()) or {};m=data["parameter_metadata"]
 for item in data["subsectors"].values():
  if abs(sum(item["components"].values())-1)>1e-6:raise PipelineContractError("component weights must sum to one")
 return data
def compose_candidate(*,subsector:str,components:dict[str,float|None],candidate:dict)->SubsectorScore:
 m=candidate["parameter_metadata"];weights=candidate["subsectors"][subsector]["components"]
 if m["approved"] is not True:return SubsectorScore(subsector,.5,0,0,m["parameter_version"],m["model_version"],ConservativeAction.REVIEW_REQUIRED,("SUBSECTOR_CANDIDATE_UNAPPROVED",))
 if any(components.get(k) is None for k in weights):return SubsectorScore(subsector,.5,0,0,m["parameter_version"],m["model_version"],ConservativeAction.REVIEW_REQUIRED,("SUBSECTOR_COMPONENT_MISSING",))
 return SubsectorScore(subsector,sum(float(components[k])*v for k,v in weights.items()),1,1,m["parameter_version"],m["model_version"],None,("SUBSECTOR_SCORE_DIAGNOSTIC",))
