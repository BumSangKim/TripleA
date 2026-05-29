from __future__ import annotations

from api.features.rebalancing.models import RebalanceRunData
from api.features.rebalancing.ports import IRebalancingRepository
from api.features.rebalancing.schemas import RebalanceRunResult


def test_rebalance_run_result_schema():
    r = RebalanceRunResult(ok=True)
    assert r.ok is True


def test_rebalance_run_data_model():
    d = RebalanceRunData(run_id=1, rows=[])
    assert d.run_id == 1


def test_irebalancing_repository_importable():
    assert IRebalancingRepository is not None
