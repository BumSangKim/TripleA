from pathlib import Path
def test_shadow_handoff_has_no_execution_surface():
 s=(Path(__file__).resolve().parents[2]/"api/score_pipeline/semiconductor_shadow_handoff.py").read_text();assert not any(x in s for x in ("broker","place_order","submit_order","target_weight"))
