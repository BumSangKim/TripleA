from __future__ import annotations

from api.features.backtests.models import BacktestRunParams
from api.features.backtests.ports import IBacktestsRepository


def test_backtest_run_params():
    p = BacktestRunParams(body={"universe": "test"})
    assert p.body["universe"] == "test"


def test_ibacktests_repository_importable():
    assert IBacktestsRepository is not None
