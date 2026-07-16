from __future__ import annotations
from dataclasses import dataclass
from api.score_pipeline.contracts import ConservativeAction
@dataclass(frozen=True)
class SemiconductorSectorScore:
 score:float;previous_score:float|None;score_change:float;stability:float;confidence:float;components:dict[str,float|None];reason_codes:tuple[str,...];parameter_version:str;model_version:str
@dataclass(frozen=True)
class SemiconductorAssetScore:
 asset_id:str;subsector:str;score:float;confidence:float;company_risk_penalty:float;competitive_position:float|None;reason_codes:tuple[str,...];fallback_state:str|None
def aggregate_sector(*,components:dict[str,float|None],previous_score:float|None,parameter_version:str,model_version:str)->SemiconductorSectorScore:
 usable=[v for v in components.values() if v is not None];score=.5 if not usable else sum(usable)/len(usable);confidence=len(usable)/len(components);change=0 if previous_score is None else score-previous_score
 return SemiconductorSectorScore(score,previous_score,change,1-abs(change),confidence,components,("SECTOR_COMPONENTS_PARTIAL" if confidence<1 else "SECTOR_COMPONENTS_COMPLETE",),parameter_version,model_version)
def score_asset(*,asset_id:str,subsector:str,subsector_score:SemiconductorSectorScore,earnings:float|None,momentum:float|None,valuation:float|None,quality:float|None,flow:float|None,company_risk_penalty:float,competitive_position:float|None)->SemiconductorAssetScore:
 vals=[subsector_score.score,earnings,momentum,valuation,quality,flow,competitive_position];usable=[v for v in vals if v is not None];confidence=len(usable)/len(vals)*subsector_score.confidence
 return SemiconductorAssetScore(asset_id,subsector,.5 if not usable else max(0,min(1,sum(usable)/len(usable)-company_risk_penalty)),confidence,company_risk_penalty,competitive_position,("ASSET_COMPETITIVE_POSITION_UNAVAILABLE",) if competitive_position is None else ("ASSET_SCORE_DIAGNOSTIC",),ConservativeAction.REVIEW_REQUIRED if competitive_position is None else None)
