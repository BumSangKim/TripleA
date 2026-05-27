from api.models import BacktestRunRequest


def test_backtest_request_accepts_testbed_fields_with_safe_defaults():
    request = BacktestRunRequest(startDate="2020-01-01", endDate="2020-02-01", initialCapital=1000)
    enabled = BacktestRunRequest(startDate="2020-01-01", endDate="2020-02-01", initialCapital=1000, enableScoreflowTestbed=True, enableDecisionLogging=True, parameterSetId="p1")
    assert request.enableScoreflowTestbed is False
    assert enabled.enableDecisionLogging is True
    assert enabled.initialSeedPolicy == "CURRENT"
