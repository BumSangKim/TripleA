from __future__ import annotations

from pathlib import Path

from api.features.orders.models import OrderDraftParams, OrderExecuteParams
from api.features.orders.service import OrdersService


class FakeRepo:
    def list_drafts(self, mode, limit): return []
    def create_draft(self, params): return {"id": 1}
    def execute_draft(self, params): return {"id": 1, "status": "executed"}


def test_list_drafts():
    assert OrdersService(FakeRepo()).list_drafts(None, 20) == []


def test_create_draft():
    result = OrdersService(FakeRepo()).create_draft(OrderDraftParams(mode="paper"))
    assert result["id"] == 1


def test_service_no_db():
    src = Path("api/features/orders/service.py").read_text()
    assert "sqlite3" not in src
    assert "get_conn" not in src
    assert "HTTPException" not in src
