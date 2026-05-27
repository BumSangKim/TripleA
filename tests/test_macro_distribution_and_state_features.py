from datetime import date

from api.strategy.macro_distribution import distribution_from_macro_decision
from api.strategy.macro_engine import MacroRegimeDecision
from api.strategy.state_features import MarketStateFeatures, PortfolioStateFeatures


def test_macro_distribution_wraps_macro_decision_and_state_features_exist():
    decision = MacroRegimeDecision(date(2026, 5, 27), "risk_off", 20, ["stress"])
    dist = distribution_from_macro_decision(decision, previous_score=50)
    market = MarketStateFeatures(.8, .3, .7, .5, .2)
    portfolio = PortfolioStateFeatures(.6, .4, .5, {"S": .2})
    assert abs(sum(dist.distribution.values()) - 1.0) < 1e-9
    assert dist.dominant_regime == "volatility_stress"
    assert market.market_stress_score == .8
    assert portfolio.sector_exposure_summary["S"] == .2
