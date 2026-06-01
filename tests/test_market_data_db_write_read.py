import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from api.market_data.models import PriceQuote
from api.market_data.repository import get_latest_price_quote, save_price_quote
from api.universe.loader import load_assets, load_universe_selectors
from api.universe.selector import resolve_all_selectors


def test_mock_price_quote_can_be_saved_and_read_back(tmp_path):
    conn = sqlite3.connect(tmp_path / "market_data.db")
    conn.row_factory = sqlite3.Row

    assets = load_assets("config/universe")
    selectors = load_universe_selectors("config/universe")
    resolved = resolve_all_selectors(assets, selectors["selectors"])
    asset = resolved["initial_order_candidate_universe"][0]
    quote = PriceQuote(
        symbol=asset["symbol"],
        market=asset["market"],
        price=Decimal("100.00"),
        currency="KRW" if asset["market"] == "KRX" else "USD",
        provider="fixture",
        as_of=datetime(2026, 5, 31, tzinfo=UTC),
        raw={"source": "fixture"},
    )

    save_price_quote(asset=asset, quote=quote, db_session=conn)
    saved = get_latest_price_quote(
        symbol=asset["symbol"],
        market=asset["market"],
        db_session=conn,
    )

    assert saved is not None
    assert saved.asset_id == asset["asset_id"]
    assert saved.symbol == asset["symbol"]
    assert saved.market == asset["market"]
    assert saved.price == Decimal(str(quote.price))
    assert saved.currency == quote.currency
    assert saved.provider == quote.provider
    assert saved.as_of == quote.as_of.isoformat()
