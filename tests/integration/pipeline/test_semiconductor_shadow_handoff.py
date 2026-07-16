from api.score_pipeline.semiconductor_shadow_handoff import build_handoff_report,render_handoff_markdown,serialize
def test_shadow_handoff_is_traceable_and_cannot_imply_production():
 r=build_handoff_report(validation={"rejection_reasons":["VALIDATION_LEAKAGE_FAILED"]});assert r["production_enabled"] is False and r["allocation_contribution"]==0 and "VALIDATION_LEAKAGE_FAILED" in serialize(r);assert "synthetic" in render_handoff_markdown(r)
