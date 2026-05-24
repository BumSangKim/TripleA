import pytest
from pydantic import ValidationError

from api.models import BacktestRunRequest


def test_dynamic_backtest_request_parses_strategy_fields():
    request = BacktestRunRequest(
        name="TripleA 3Y Backtest",
        startDate="2023-05-24",
        endDate="2026-05-24",
        initialCapital=10_000_000,
        strategyMode="triplea_dynamic",
        riskProfile="balanced",
        universeId="default_global",
        rebalanceFrequency="monthly",
        feeBps=5,
        slippageBps=5,
        taxBps=0,
    )

    assert request.strategyMode == "triplea_dynamic"
    assert request.riskProfile == "balanced"
    assert request.universeId == "default_global"
    assert request.baseCurrency == "KRW"
    assert request.dataLookbackYears == 5


def test_dynamic_backtest_request_rejects_manual_targets():
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            name="Bad request",
            startDate="2023-05-24",
            endDate="2026-05-24",
            initialCapital=10_000_000,
            strategyMode="triplea_dynamic",
            riskProfile="balanced",
            universeId="default_global",
            targets=[{"assetClass": "SPY", "targetRatio": 1}],
        )
