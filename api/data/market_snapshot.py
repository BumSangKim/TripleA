from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

@dataclass(frozen=True)
class MarketPriceSnapshotRow:
    asset_id:str; observed_at:date; available_at:datetime; price:float; currency:str; source:str; as_of_date:date; quality_score:float=1.0; is_stale:bool=False
@dataclass(frozen=True)
class FxSnapshotRow:
    base_currency:str; quote_currency:str; observed_at:date; available_at:datetime; rate:float; source:str; as_of_date:date; quality_score:float=1.0; is_stale:bool=False
@dataclass(frozen=True)
class MarketSnapshot:
    decision_time:datetime; prices:tuple[MarketPriceSnapshotRow,...]; fx_rates:tuple[FxSnapshotRow,...]
class MarketSnapshotReader(Protocol):
    def read_market_snapshot(self, *, decision_time:datetime)->MarketSnapshot: ...
class FixtureMarketSnapshotReader:
    def __init__(self,prices:tuple[MarketPriceSnapshotRow,...],fx_rates:tuple[FxSnapshotRow,...])->None:self._p=prices;self._f=fx_rates
    def read_market_snapshot(self,*,decision_time:datetime)->MarketSnapshot:
        return MarketSnapshot(decision_time,tuple(x for x in self._p if x.available_at<=decision_time),tuple(x for x in self._f if x.available_at<=decision_time))
