from __future__ import annotations

from api.features.dashboard.models import DashboardData
from api.features.dashboard.ports import IDashboardRepository


def test_model_instantiation():
    data = DashboardData(
        mode=None, mode_info=None, kpi=None, macro=[], accounts=[],
        allocation=[], targets=[], suggestions=[], top_movers=[],
        calendar=[], alerts=[], insights=None,
    )
    assert data.macro == []


def test_protocol_import():
    assert IDashboardRepository is not None
