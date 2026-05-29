from __future__ import annotations

from .base import BaseDataProvider
from .live import LiveTradingProvider
from .mock import BacktestProvider, MockProvider, TestProvider
from .modes import TradingMode, get_mode_policy, normalize_mode
from .paper import PaperTradingProvider


class ProviderRouter:
    _provider_types: dict[TradingMode, type[BaseDataProvider]] = {
        TradingMode.MOCK: MockProvider,
        TradingMode.TEST: TestProvider,
        TradingMode.BACKTEST: BacktestProvider,
        TradingMode.PAPER: PaperTradingProvider,
        TradingMode.LIVE: LiveTradingProvider,
    }

    def get(self, mode: str | TradingMode | None) -> BaseDataProvider:
        trading_mode = normalize_mode(mode)
        provider_type = self._provider_types[trading_mode]
        return provider_type(get_mode_policy(trading_mode))

    def list(self) -> list[BaseDataProvider]:
        return [self.get(mode) for mode in TradingMode]


provider_router = ProviderRouter()
