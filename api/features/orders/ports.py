from __future__ import annotations

from typing import Any, Optional, Protocol

from api.features.orders.models import OrderDraftParams, OrderExecuteParams


class IOrdersRepository(Protocol):
    def list_drafts(self, mode: Optional[Any], limit: int) -> list[Any]: ...
    def create_draft(self, params: OrderDraftParams) -> Any: ...
    def execute_draft(self, params: OrderExecuteParams) -> Any: ...
