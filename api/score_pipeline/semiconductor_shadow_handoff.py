from __future__ import annotations
import json
def build_handoff_report(*,validation:dict)->dict:
 return {"report_version":"semiconductor_shadow_handoff_v1","evidence":"synthetic_fixture_validation_only","approved":False,"production_enabled":False,"allocation_contribution":0.0,"parameter_version":"semiconductor_shadow_tilt_v1","model_version":"semiconductor_shadow_handoff_v1","validation":validation,"reason_codes":["SEMICONDUCTOR_SHADOW_ONLY","REAL_HISTORICAL_EVIDENCE_REQUIRED"],"warnings":["No production approval or factual outperformance claim."]}
def render_handoff_markdown(report:dict)->str:return "# Semiconductor Shadow Handoff\n\n- Evidence: synthetic fixture validation only\n- Approved: false\n- Production enabled: false\n- Allocation contribution: 0.0\n"
def serialize(report:dict)->str:return json.dumps(report,sort_keys=True,indent=2)+"\n"
