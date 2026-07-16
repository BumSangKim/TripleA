from api.score_pipeline.semiconductor_macro_risk_components import build_macro_risk_components
def test_macro_and_risk_components_remain_separate_from_hard_constraints():
 x=build_macro_risk_components(regime_distribution={"a":1.0},macro_sensitivities={"a":.5},risk_inputs={"drawdown":.2},geopolitical_metadata={"status":"provided"},parameter_version="v1",model_version="v1");assert x.macro_fit==.5 and x.risk_penalty==.2;assert not hasattr(x,"allocation") and not hasattr(x,"hard_constraint")
