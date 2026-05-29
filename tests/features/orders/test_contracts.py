from __future__ import annotations

from api.features.orders.models import OrderDraftParams, OrderExecuteParams
from api.features.orders.ports import IOrdersRepository


def test_order_draft_params():
    p = OrderDraftParams(mode="paper")
    assert p.mode == "paper"
    assert p.source == "rebalancing"


def test_order_execute_params():
    p = OrderExecuteParams(mode="paper", order_draft_id=1)
    assert p.order_draft_id == 1


def test_iorders_repository_importable():
    assert IOrdersRepository is not None
