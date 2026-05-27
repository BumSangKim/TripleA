from datetime import date

from api.strategy.macro_distribution import MacroRegimeDistribution
from api.strategy.regime_response_engine import RegimeResponseEngine
from api.strategy.state_features import MarketStateFeatures, PortfolioStateFeatures


def test_regime_response_produces_offsets_without_orders():
    macro = MacroRegimeDistribution(date(2026, 5, 27), {"volatility_stress": .8}, "volatility_stress", .8, .8, .4, .4, [])
    market = MarketStateFeatures(.9, .2, .8, .6, .2)
    portfolio = PortfolioStateFeatures(.8, .5, .7)
    decision = RegimeResponseEngine().decide(macro, market, portfolio)
    assert decision.response_mode == "DEFEND"
    assert decision.permissions.risk_increase_buy == "BLOCK"
    assert decision.offsets.risk.aggressive_alpha_max_offset < 0
