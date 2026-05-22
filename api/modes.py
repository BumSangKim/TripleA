"""Trading mode policy helpers.

Modes separate mock/test/backtest/paper/live behavior so API handlers can make
conservative decisions before touching external providers or order endpoints.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TradingMode(str, Enum):
    MOCK = "mock"
    TEST = "test"
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


@dataclass(frozen=True)
class ModePolicy:
    mode: TradingMode
    provider: str
    db_write_scope: str
    external_api: bool
    order_policy: str

    @property
    def can_write_user_data(self) -> bool:
        return self.db_write_scope in {"user_data", "results"}

    @property
    def can_execute_orders(self) -> bool:
        return self.order_policy in {"paper_order", "manual_live_order"}


MODE_POLICIES: dict[TradingMode, ModePolicy] = {
    TradingMode.MOCK: ModePolicy(
        mode=TradingMode.MOCK,
        provider="MockProvider",
        db_write_scope="read_only",
        external_api=False,
        order_policy="disabled",
    ),
    TradingMode.TEST: ModePolicy(
        mode=TradingMode.TEST,
        provider="TestProvider",
        db_write_scope="read_only",
        external_api=False,
        order_policy="disabled",
    ),
    TradingMode.BACKTEST: ModePolicy(
        mode=TradingMode.BACKTEST,
        provider="BacktestProvider",
        db_write_scope="results",
        external_api=False,
        order_policy="disabled",
    ),
    TradingMode.PAPER: ModePolicy(
        mode=TradingMode.PAPER,
        provider="PaperTradingProvider",
        db_write_scope="user_data",
        external_api=True,
        order_policy="paper_order",
    ),
    TradingMode.LIVE: ModePolicy(
        mode=TradingMode.LIVE,
        provider="LiveTradingProvider",
        db_write_scope="user_data",
        external_api=True,
        order_policy="read_only_until_manual_approval",
    ),
}


def normalize_mode(mode: str | TradingMode | None) -> TradingMode:
    if isinstance(mode, TradingMode):
        return mode
    value = (mode or TradingMode.PAPER.value).strip().lower()
    try:
        return TradingMode(value)
    except ValueError as exc:
        allowed = ", ".join(m.value for m in TradingMode)
        raise ValueError(f"Unsupported mode '{mode}'. Allowed modes: {allowed}") from exc


def get_mode_policy(mode: str | TradingMode | None) -> ModePolicy:
    return MODE_POLICIES[normalize_mode(mode)]
