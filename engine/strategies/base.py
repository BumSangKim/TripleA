"""Base strategy interfaces."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Signal:
    indicator: str
    signal_type: str
    strategy: str
    confidence: float
    price: float | None = None
    detail: str | None = None


@dataclass(frozen=True)
class BacktestResult:
    strategy: str
    total_return: float
    trades: int
    win_rate: float | None = None


class BaseStrategy(ABC):
    """매매 신호 생성 전략 기반 클래스."""

    name: str = "base"

    @abstractmethod
    def generate(self, features: dict) -> dict | None:
        """Generate one signal dict from a feature snapshot, or None."""

    def generate_signals(self, features: pd.DataFrame) -> list[Signal]:
        """DataFrame 기반 전략 인터페이스. 기본 구현은 마지막 row만 평가한다."""
        if features.empty:
            return []
        signal = self.generate(features.iloc[-1].to_dict())
        return [Signal(**signal)] if signal else []

    def backtest(self, historical_data: pd.DataFrame, parameters: dict | None = None) -> BacktestResult:
        """Override in concrete strategies when a full backtest is needed."""
        return BacktestResult(strategy=self.name, total_return=0.0, trades=0)


Strategy = BaseStrategy

