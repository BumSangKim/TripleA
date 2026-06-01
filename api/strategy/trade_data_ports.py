from __future__ import annotations

from datetime import date
from typing import Protocol

from api.domain.trade_data import TradeSnapshot


class TradeSnapshotReader(Protocol):
    def get_trade_snapshot(
        self,
        as_of_date: date,
        *,
        lookback_months: int = 60,
    ) -> TradeSnapshot:
        ...
