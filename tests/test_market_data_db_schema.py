import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from api.market_data.models import PriceQuote
from api.market_data.repository import (
    ensure_price_quote_table,
    get_latest_price_quote,
    save_price_quote,
)


def _conn(path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def test_price_quote_table_can_be_created_in_test_db(tmp_path):
    conn = _conn(tmp_path / "market_data.db")

    ensure_price_quote_table(conn)

    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "price_quotes" in tables


def test_save_and_read_latest_price_quote_preserves_decimal_and_raw_json(tmp_path):
    conn = _conn(tmp_path / "market_data.db")
    asset = {"asset_id": "KRX_360750", "symbol": "360750", "market": "KRX"}
    quote = PriceQuote(
        symbol="360750",
        market="KRX",
        price=Decimal("12345.67"),
        currency="KRW",
        provider="mock",
        as_of=datetime(2026, 5, 27, 9, 1, tzinfo=UTC),
        trade_date="2026-05-27",
        raw={"stck_prpr": "12345.67"},
    )

    saved = save_price_quote(asset=asset, quote=quote, db_session=conn)
    latest = get_latest_price_quote(symbol="360750", market="KRX", db_session=conn)

    assert saved.id > 0
    assert latest is not None
    assert latest.asset_id == "KRX_360750"
    assert latest.price == Decimal("12345.67")
    assert latest.raw == {"stck_prpr": "12345.67"}
