from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PriceQuote:
    symbol: str
    market: str
    price: Decimal
    currency: str
    provider: str
    as_of: datetime | None = None
    trade_date: str | None = None
    raw: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "price", Decimal(str(self.price)))
