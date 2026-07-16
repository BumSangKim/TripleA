from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
from api.score_pipeline.contracts import ConservativeAction,PipelineContractError
@dataclass(frozen=True)
class SemiconductorMacroRiskComponents:
 macro_fit:float; risk_penalty:float; confidence:float; regime_distribution:Mapping[str,float]; parameter_version:str; model_version:str; reason_codes:tuple[str,...]=(); fallback_state:str|None=None
 def __post_init__(self):
  if not self.regime_distribution or abs(sum(self.regime_distribution.values())-1)>1e-6:raise PipelineContractError("full regime distribution must sum to one")
  if not all(0<=x<=1 for x in (*self.regime_distribution.values(),self.macro_fit,self.risk_penalty,self.confidence)):raise PipelineContractError("components must be ratios")
  if self.fallback_state and self.fallback_state not in ConservativeAction.values():raise PipelineContractError("fallback must be conservative")
def build_macro_risk_components(*,regime_distribution:Mapping[str,float],macro_sensitivities:Mapping[str,float],risk_inputs:Mapping[str,float|None],geopolitical_metadata:Mapping[str,object]|None,parameter_version:str,model_version:str)->SemiconductorMacroRiskComponents:
 if set(regime_distribution)!=set(macro_sensitivities):raise PipelineContractError("macro sensitivities must cover full regime distribution")
 macro_fit=sum(regime_distribution[k]*macro_sensitivities[k] for k in regime_distribution)
 usable=[float(v) for v in risk_inputs.values() if v is not None];missing=len(usable)!=len(risk_inputs) or not geopolitical_metadata
 penalty=sum(usable)/len(usable) if usable else 0.;confidence=(len(usable)/len(risk_inputs) if risk_inputs else 0.)*(0.8 if missing else 1.)
 return SemiconductorMacroRiskComponents(macro_fit,penalty,confidence,dict(regime_distribution),parameter_version,model_version,("SEMICONDUCTOR_MACRO_RISK_COMPONENTS",) if not missing else ("SEMICONDUCTOR_MACRO_RISK_REVIEW_REQUIRED",),ConservativeAction.REVIEW_REQUIRED if missing else None)
