"""Mode-aware data provider routing for the dashboard API.

The router is intentionally thin for now: it centralizes mode policy and keeps
the API layer from knowing whether a request is mock, backtest, paper, or live.
Concrete providers can later swap DB reads for broker/API reads without
changing endpoint contracts.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .models import AccountSummary, AllocationItem, ModeInfo, TargetItem, TopMover
from .modes import ModePolicy, TradingMode, get_mode_policy, normalize_mode
from .services import (
    get_accounts_from_db,
    get_allocation_from_holdings,
    get_target_deviations,
    get_top_movers_from_db,
)


@dataclass(frozen=True)
class ProviderCapabilities:
    mode: TradingMode
    provider: str
    can_write_user_data: bool
    can_execute_orders: bool
    external_api: bool
    order_policy: str


class BaseDataProvider:
    """Read facade shared by all trading modes."""

    def __init__(self, policy: ModePolicy):
        self.policy = policy

    @property
    def mode(self) -> TradingMode:
        return self.policy.mode

    @property
    def name(self) -> str:
        return self.policy.provider

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            mode=self.policy.mode,
            provider=self.policy.provider,
            can_write_user_data=self.policy.can_write_user_data,
            can_execute_orders=self.policy.can_execute_orders,
            external_api=self.policy.external_api,
            order_policy=self.policy.order_policy,
        )

    def mode_info(self) -> ModeInfo:
        return ModeInfo(
            mode=self.policy.mode,
            provider=self.policy.provider,
            dbWriteScope=self.policy.db_write_scope,
            externalApi=self.policy.external_api,
            orderPolicy=self.policy.order_policy,
            canWriteUserData=self.policy.can_write_user_data,
            canExecuteOrders=self.policy.can_execute_orders,
        )

    def assert_user_write_allowed(self) -> None:
        if not self.policy.can_write_user_data:
            raise PermissionError(f"{self.mode.value} mode is read-only")

    def get_accounts(self, conn: sqlite3.Connection) -> list[AccountSummary]:
        return get_accounts_from_db(conn)

    def get_target_deviations(self, conn: sqlite3.Connection) -> list[TargetItem]:
        return get_target_deviations(conn, self.mode)

    def get_allocation(self, conn: sqlite3.Connection) -> list[AllocationItem]:
        return get_allocation_from_holdings(conn)

    def get_top_movers(self, conn: sqlite3.Connection) -> list[TopMover]:
        return get_top_movers_from_db(conn)


class MockProvider(BaseDataProvider):
    pass


class TestProvider(BaseDataProvider):
    pass


class BacktestProvider(BaseDataProvider):
    pass


class PaperTradingProvider(BaseDataProvider):
    pass


class LiveTradingProvider(BaseDataProvider):
    pass


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
