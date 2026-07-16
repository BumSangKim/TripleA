import pytest
from api.score_pipeline.contracts import PipelineContractError
from api.score_pipeline.semiconductor_macro_risk_components import build_macro_risk_components
def test_full_distribution_and_missing_geopolitical_data_stay_non_allocating():
 x=build_macro_risk_components(regime_distribution={"a":.4,"b":.6},macro_sensitivities={"a":.2,"b":.8},risk_inputs={"volatility":.3,"liquidity":None},geopolitical_metadata=None,parameter_version="v1",model_version="v1");assert x.macro_fit==pytest.approx(.56);assert x.fallback_state=="REVIEW_REQUIRED";assert x.risk_penalty==.3
def test_partial_distribution_is_rejected():
 with pytest.raises(PipelineContractError):build_macro_risk_components(regime_distribution={"a":1},macro_sensitivities={"b":1},risk_inputs={},geopolitical_metadata={},parameter_version="v",model_version="v")
