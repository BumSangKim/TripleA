from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class ShadowTiltCandidate: opportunity_score:float;risk_budget:float;active_tilt:float;diagnostic_only:bool;production_enabled:bool;allocation_contribution:float;reason_codes:tuple[str,...]
def calculate_shadow_tilt(*,opportunity_score:float,risk_budget:float,quality:float,confidence:float,concentration_risk:float,minimum:float,base:float,maximum:float)->ShadowTiltCandidate:
 continuous=max(0,min(1,opportunity_score))*max(0,min(1,risk_budget))*max(0,min(1,quality))*max(0,min(1,confidence))*(1-max(0,min(1,concentration_risk)))
 return ShadowTiltCandidate(opportunity_score,risk_budget,min(maximum,max(minimum,base+continuous*(maximum-base))),True,False,0.,("SHADOW_TILT_DIAGNOSTIC_ONLY",))
