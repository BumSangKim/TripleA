from __future__ import annotations

from typing import Any, Optional

from api.features.orders.models import OrderDraftParams, OrderExecuteParams
from api.features.orders.ports import IOrdersRepository


class OrdersService:
    def __init__(self, repo: IOrdersRepository) -> None:
        self._repo = repo

    def list_drafts(self, mode: Optional[Any], limit: int) -> list[Any]:
        return self._repo.list_drafts(mode, limit)

    def create_draft(self, params: OrderDraftParams) -> Any:
        return self._repo.create_draft(params)

    def execute_draft(self, params: OrderExecuteParams) -> Any:
        return self._repo.execute_draft(params)
