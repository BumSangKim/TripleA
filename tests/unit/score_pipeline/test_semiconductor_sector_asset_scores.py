from api.score_pipeline.semiconductor_sector_asset_scores import aggregate_sector,score_asset
def test_sector_and_asset_outputs_are_distinct_and_missing_competitive_field_lowers_confidence():
 s=aggregate_sector(components={"demand":.7,"supply":.5},previous_score=.5,parameter_version="v",model_version="v");a=score_asset(asset_id="US_NVDA",subsector="ai_fabless",subsector_score=s,earnings=.6,momentum=.6,valuation=.5,quality=.8,flow=.4,company_risk_penalty=.1,competitive_position=None);assert s.score!=a.score and a.fallback_state=="REVIEW_REQUIRED" and a.confidence<s.confidence
