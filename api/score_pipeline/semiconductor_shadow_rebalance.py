from dataclasses import dataclass
from api.score_pipeline.contracts import ConservativeAction
@dataclass(frozen=True)
class SemiconductorRebalancePlan: intensity:float;action:str;new_cash_first:bool;hard_constraint_passed:bool;confidence:float;reason_codes:tuple[str,...];warnings:tuple[str,...]
def review_rebalance(*,drift:float,conviction_change:float,risk_pressure:float,confidence:float,new_cash:float,cost_efficiency:float,turnover_penalty:float,hard_constraint_passed:bool,per_cap:float,monthly_cap:float)->SemiconductorRebalancePlan:
 if not hard_constraint_passed:return SemiconductorRebalancePlan(0,ConservativeAction.REVIEW_REQUIRED,True,False,0,("HARD_CONSTRAINT_BLOCKED",),("tax_policy_unavailable",))
 intensity=min(per_cap,monthly_cap,max(0,drift+conviction_change-risk_pressure-turnover_penalty)*max(0,min(1,confidence))*max(0,min(1,cost_efficiency)))
 action=ConservativeAction.REVIEW_REQUIRED if intensity else ConservativeAction.HOLD
 return SemiconductorRebalancePlan(intensity,action,new_cash>0,True,max(0,min(1,confidence)),("NEW_CASH_FIRST" if new_cash>0 else "REVIEW_ONLY_REBALANCE",),("tax_policy_unavailable",))
