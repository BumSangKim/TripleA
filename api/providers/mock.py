from __future__ import annotations

import sqlite3

from api.features.system.schemas import ProviderSyncResult

from .base import BaseDataProvider


def _local_read_only_sync(provider: BaseDataProvider, conn: sqlite3.Connection) -> ProviderSyncResult:
    accounts = provider.get_accounts(conn)
    total_value = sum(float(account.value or 0) for account in accounts)
    cash_value = 0.0
    try:
        cash_value = float(
            conn.execute(
                """
                SELECT COALESCE(SUM(market_value), 0) AS total
                FROM holdings
                WHERE asset_class='현금'
                """
            ).fetchone()["total"]
            or 0
        )
    except sqlite3.Error:
        cash_value = 0.0
    return ProviderSyncResult(
        ok=True,
        mode=provider.mode,
        provider=provider.name,
        syncedPositions=0,
        totalValue=total_value,
        cashValue=cash_value,
        message="No external account sync is configured for this mode; local read-only state was refreshed.",
    )


class MockProvider(BaseDataProvider):
    def sync_accounts(self, conn: sqlite3.Connection) -> ProviderSyncResult:
        return _local_read_only_sync(self, conn)


class TestProvider(BaseDataProvider):
    def sync_accounts(self, conn: sqlite3.Connection) -> ProviderSyncResult:
        return _local_read_only_sync(self, conn)


class BacktestProvider(BaseDataProvider):
    def sync_accounts(self, conn: sqlite3.Connection) -> ProviderSyncResult:
        return _local_read_only_sync(self, conn)
