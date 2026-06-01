from __future__ import annotations

import sqlite3
from datetime import date

from api.bottleneck_data_service import get_bottleneck_snapshot, get_sector_asset_mappings
from api.domain.strategy_inputs import (
    BottleneckIndicatorInput,
    BottleneckSnapshotInput,
    MacroIndicatorInput,
    MacroSnapshotInput,
    PriceHistoryPointInput,
    SectorAssetMappingInput,
)
from api.macro_data_service import get_macro_snapshot


class SqliteMacroSnapshotReader:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def read_macro_snapshot(self, as_of_date: date) -> MacroSnapshotInput:
        snapshot = get_macro_snapshot(self.conn, as_of_date)
        return MacroSnapshotInput(
            as_of_date=snapshot.as_of_date,
            indicators={
                key: MacroIndicatorInput(
                    indicator=item.indicator,
                    value=item.value,
                    unit=item.unit,
                    data_date=item.data_date,
                    source=item.source,
                )
                for key, item in snapshot.indicators.items()
            },
        )


class SqliteBottleneckSnapshotReader:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def read_bottleneck_snapshot(
        self,
        as_of_date: date,
        *,
        lookback_months: int,
    ) -> BottleneckSnapshotInput:
        snapshot = get_bottleneck_snapshot(
            self.conn,
            as_of_date,
            lookback_months=lookback_months,
        )
        return BottleneckSnapshotInput(
            as_of_date=snapshot.as_of_date,
            lookback_months=snapshot.lookback_months,
            indicators=[
                BottleneckIndicatorInput(
                    indicator_key=item.indicator_key,
                    indicator_name=item.indicator_name,
                    sector_code=item.sector_code,
                    value_date=item.value_date,
                    release_date=item.release_date,
                    value=item.value,
                    unit=item.unit,
                    source=item.source,
                    layer=item.layer,
                )
                for item in snapshot.indicators
            ],
        )


class SqliteSectorAssetMappingReader:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def read_sector_asset_mappings(self) -> dict[str, list[SectorAssetMappingInput]]:
        mappings = get_sector_asset_mappings(self.conn)
        return {
            sector_code: [
                SectorAssetMappingInput(
                    sector_code=item.sector_code,
                    asset_code=item.asset_code,
                    asset_name=item.asset_name,
                    asset_type=item.asset_type,
                    currency=item.currency,
                    priority=item.priority,
                )
                for item in items
            ]
            for sector_code, items in mappings.items()
        }


class SqlitePriceHistoryReader:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def read_price_history(
        self,
        asset_code: str,
        *,
        start_date: date,
        end_date: date,
    ) -> list[PriceHistoryPointInput]:
        if not _table_exists(self.conn, "market_prices"):
            return []
        rows = self.conn.execute(
            """
            SELECT asset_code, price_date, COALESCE(adj_close, close) AS price
            FROM market_prices
            WHERE asset_code=?
              AND price_date BETWEEN ? AND ?
            ORDER BY price_date ASC
            """,
            (asset_code, start_date.isoformat(), end_date.isoformat()),
        ).fetchall()
        return [
            PriceHistoryPointInput(
                asset_code=row["asset_code"],
                price_date=date.fromisoformat(row["price_date"][:10]),
                price=float(row["price"]),
            )
            for row in rows
            if row["price"] is not None
        ]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)

