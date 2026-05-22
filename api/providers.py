"""Mode-aware data provider routing for the dashboard API.

The router is intentionally thin for now: it centralizes mode policy and keeps
the API layer from knowing whether a request is mock, backtest, paper, or live.
Concrete providers can later swap DB reads for broker/API reads without
changing endpoint contracts.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .kis import KISBalanceSnapshot, KISClient, load_kis_config
from .models import AccountSummary, AllocationItem, ModeInfo, ProviderSyncResult, TargetItem, TopMover
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

    def sync_accounts(self, conn: sqlite3.Connection) -> ProviderSyncResult:
        raise NotImplementedError(f"{self.name} does not support account sync yet")


class MockProvider(BaseDataProvider):
    pass


class TestProvider(BaseDataProvider):
    pass


class BacktestProvider(BaseDataProvider):
    pass


class PaperTradingProvider(BaseDataProvider):
    def sync_accounts(self, conn: sqlite3.Connection) -> ProviderSyncResult:
        config = load_kis_config(force_demo=True)
        snapshot = KISClient(config).fetch_domestic_balance()
        account_id = _upsert_kis_snapshot(
            conn,
            snapshot=snapshot,
            account_name=config.account_name,
            account_type=config.account_type,
            data_source="KIS_PAPER",
            trade_status="PAPER_READ_ONLY",
        )
        return ProviderSyncResult(
            ok=True,
            mode=self.mode,
            provider=self.name,
            accountId=account_id,
            accountMasked=snapshot.account_masked,
            syncedPositions=len(snapshot.positions),
            totalValue=snapshot.total_value,
            cashValue=snapshot.cash_value,
            message=snapshot.message or "KIS paper account synced",
        )


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


def _upsert_kis_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot: KISBalanceSnapshot,
    account_name: str,
    account_type: str,
    data_source: str,
    trade_status: str,
) -> int:
    now = conn.execute("SELECT datetime('now','localtime')").fetchone()[0]
    existing = conn.execute(
        """
        SELECT id FROM accounts
        WHERE broker='KIS' AND data_source=? AND name=?
        ORDER BY id LIMIT 1
        """,
        (data_source, account_name),
    ).fetchone()

    if existing:
        account_id = int(existing["id"])
        conn.execute(
            """
            UPDATE accounts
            SET type=?, account_type=?, initial_value=?, connection_status='CONNECTED',
                trade_status=?, last_synced_at=?
            WHERE id=?
            """,
            (account_type, account_type, snapshot.total_value, trade_status, now, account_id),
        )
    else:
        cur = conn.execute(
            """
            INSERT INTO accounts
            (name, type, account_type, broker, initial_value, connection_status,
             trade_status, include_in_rebalancing, data_source, last_synced_at)
            VALUES (?, ?, ?, 'KIS', ?, 'CONNECTED', ?, 1, ?, ?)
            """,
            (account_name, account_type, account_type, snapshot.total_value, trade_status, data_source, now),
        )
        account_id = int(cur.lastrowid)

    conn.execute("DELETE FROM holdings WHERE account_id=?", (account_id,))
    for position in snapshot.positions:
        conn.execute(
            """
            INSERT INTO holdings
            (account_id, ticker, name, quantity, avg_price, current_price,
             market_value, profit, asset_class, price, value, strategy_bucket, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BROKER_SYNC', ?)
            """,
            (
                account_id,
                position.code,
                position.name,
                position.quantity,
                position.avg_price,
                position.current_price,
                position.market_value,
                position.profit,
                position.asset_class,
                position.current_price,
                position.market_value,
                now,
            ),
        )

    conn.execute(
        """
        INSERT INTO account_snapshots
        (account_id, total_value, cash_value, domestic_stock_value, bond_value, etf_value, snapshot_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            account_id,
            snapshot.total_value,
            snapshot.cash_value,
            snapshot.domestic_stock_value,
            snapshot.bond_value,
            snapshot.etf_value,
            now,
        ),
    )
    conn.commit()
    return account_id
