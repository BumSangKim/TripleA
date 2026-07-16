def characterize_candidate(metrics:dict)->dict:
 checks={"leakage":not metrics.get("leakage_detected",False),"stability":not metrics.get("unstable",False),"turnover":not metrics.get("excessive_turnover",False),"concentration":not metrics.get("single_asset_dominance",False),"drawdown":not metrics.get("drawdown_deterioration",False),"cycles":metrics.get("memory_cycle_count",0)>=2,"explainability":bool(metrics.get("explanation_complete"))}
 reasons=[f"VALIDATION_{name.upper()}_FAILED" for name,passed in checks.items() if not passed]
 return {"parameter_version":"semiconductor_validation_candidate_v1","production_enabled":False,"approval_required":True,"checks":checks,"rejection_reasons":reasons,"summary":"characterization only; no owner-approved production thresholds"}
