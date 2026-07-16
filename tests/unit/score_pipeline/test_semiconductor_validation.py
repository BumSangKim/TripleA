from api.score_pipeline.semiconductor_validation import characterize_candidate
def test_validation_rejects_known_failure_modes_and_stays_disabled():
 r=characterize_candidate({"leakage_detected":True,"unstable":True,"excessive_turnover":True,"single_asset_dominance":True,"drawdown_deterioration":True,"memory_cycle_count":1,"explanation_complete":False});assert r["production_enabled"] is False and len(r["rejection_reasons"])==7
