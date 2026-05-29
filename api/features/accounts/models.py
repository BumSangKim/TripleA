from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class HoldingRow:
    account_name: str
    ticker: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
