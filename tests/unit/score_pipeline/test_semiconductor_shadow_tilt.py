from api.score_pipeline.semiconductor_shadow_tilt import calculate_shadow_tilt
def test_shadow_tilt_is_continuous_and_quality_or_concentration_cannot_increase_it():
 hi=calculate_shadow_tilt(opportunity_score=1,risk_budget=1,quality=1,confidence=1,concentration_risk=0,minimum=0,base=.05,maximum=.15);low=calculate_shadow_tilt(opportunity_score=1,risk_budget=1,quality=.2,confidence=.2,concentration_risk=.8,minimum=0,base=.05,maximum=.15);assert hi.active_tilt>low.active_tilt and hi.allocation_contribution==0 and hi.production_enabled is False
