from __future__ import annotations

import sqlite3

from api.brokers.kis.client import KISClient
from api.brokers.kis.config import load_kis_config
from api.features.system.schemas import ProviderSyncResult
from ._upsert import upsert_kis_snapshot
from .base import BaseDataProvider


class LiveTradingProvider(BaseDataProvider):
    def sync_accounts(self, conn: sqlite3.Connection) -> ProviderSyncResult:
        config = load_kis_config(force_demo=False)
        snapshot = KISClient(config).fetch_domestic_balance()
        account_id = upsert_kis_snapshot(
            conn,
            snapshot=snapshot,
            account_name=config.account_name,
            account_type=config.account_type,
            data_source="KIS_LIVE",
            trade_status="LIVE_READ_ONLY",
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
            message=snapshot.message or "KIS live account synced in read-only mode",
        )
