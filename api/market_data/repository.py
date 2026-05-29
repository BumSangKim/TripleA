from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from api.db import connection as api_db
from api.market_data.models import PriceQuote


@dataclass(frozen=True)
class PriceQuoteRecord:
    id: int
    asset_id: str
    symbol: str
    market: str
    price: Decimal
    currency: str
    provider: str
    as_of: str | None
    trade_date: str | None
    raw: dict[str, Any] | None
    created_at: str


def ensure_price_quote_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS price_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            market TEXT NOT NULL,
            price TEXT NOT NULL,
            currency TEXT NOT NULL,
            provider TEXT NOT NULL,
            as_of TEXT,
            trade_date TEXT,
            raw_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_price_quotes_latest
        ON price_quotes(symbol, market, provider, as_of, trade_date, created_at);
        """
    )
    conn.commit()


def save_price_quote(
    *,
    asset: dict[str, Any],
    quote: PriceQuote,
    db_session: sqlite3.Connection | None = None,
) -> PriceQuoteRecord:
    if db_session is None:
        with api_db.get_conn() as conn:
            return _save_price_quote(conn=conn, asset=asset, quote=quote)
    return _save_price_quote(conn=db_session, asset=asset, quote=quote)


def get_latest_price_quote(
    *,
    symbol: str,
    market: str,
    db_session: sqlite3.Connection | None = None,
) -> PriceQuoteRecord | None:
    if db_session is None:
        with api_db.get_conn() as conn:
            return _get_latest_price_quote(conn=conn, symbol=symbol, market=market)
    return _get_latest_price_quote(conn=db_session, symbol=symbol, market=market)


def _save_price_quote(
    *,
    conn: sqlite3.Connection,
    asset: dict[str, Any],
    quote: PriceQuote,
) -> PriceQuoteRecord:
    ensure_price_quote_table(conn)
    cursor = conn.execute(
        """
        INSERT INTO price_quotes (
            asset_id, symbol, market, price, currency, provider, as_of, trade_date, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset["asset_id"],
            quote.symbol,
            quote.market,
            str(quote.price),
            quote.currency,
            quote.provider,
            quote.as_of.isoformat() if quote.as_of else None,
            quote.trade_date,
            json.dumps(quote.raw, ensure_ascii=False, sort_keys=True) if quote.raw is not None else None,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM price_quotes WHERE id=?",
        (cursor.lastrowid,),
    ).fetchone()
    return _record_from_row(row)


def _get_latest_price_quote(
    *,
    conn: sqlite3.Connection,
    symbol: str,
    market: str,
) -> PriceQuoteRecord | None:
    ensure_price_quote_table(conn)
    row = conn.execute(
        """
        SELECT *
        FROM price_quotes
        WHERE symbol=? AND market=?
        ORDER BY COALESCE(as_of, trade_date, created_at) DESC, id DESC
        LIMIT 1
        """,
        (symbol, market),
    ).fetchone()
    return _record_from_row(row) if row else None


def _record_from_row(row: sqlite3.Row | tuple[Any, ...]) -> PriceQuoteRecord:
    data = dict(row) if isinstance(row, sqlite3.Row) else _tuple_row_to_dict(row)
    raw_json = data.get("raw_json")
    return PriceQuoteRecord(
        id=int(data["id"]),
        asset_id=data["asset_id"],
        symbol=data["symbol"],
        market=data["market"],
        price=Decimal(str(data["price"])),
        currency=data["currency"],
        provider=data["provider"],
        as_of=data.get("as_of"),
        trade_date=data.get("trade_date"),
        raw=json.loads(raw_json) if raw_json else None,
        created_at=data["created_at"],
    )


def _tuple_row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    columns = [
        "id",
        "asset_id",
        "symbol",
        "market",
        "price",
        "currency",
        "provider",
        "as_of",
        "trade_date",
        "raw_json",
        "created_at",
    ]
    return dict(zip(columns, row, strict=True))
