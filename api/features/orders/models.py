from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class OrderDraftParams:
    mode: str
    source: str = "rebalancing"
    max_order_amount: Optional[float] = None


@dataclass
class OrderExecuteParams:
    mode: str
    order_draft_id: int
    confirm_text: str = ""
