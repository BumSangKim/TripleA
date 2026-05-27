import os
import sqlite3
from decimal import Decimal

import pytest

from api.market_data.price_provider import get_default_price_provider
from api.market_data.repository import get_latest_price_quote, save_price_quote
from api.universe.loader import load_assets, load_universe_selectors
from api.universe.selector import resolve_all_selectors

pytestmark = [pytest.mark.integration, pytest.mark.live_price, pytest.mark.db_integration]


def test_universe_live_price_query_can_be_saved_and_read_back(tmp_path):
    if os.getenv("RUN_LIVE_PRICE_SMOKE") != "1" or os.getenv("RUN_DB_INTEGRATION") != "1":
        pytest.skip("Set RUN_LIVE_PRICE_SMOKE=1 and RUN_DB_INTEGRATION=1 to run live DB e2e test")

    assets = load_assets("config/universe")
    selectors = load_universe_selectors("config/universe")
    resolved = resolve_all_selectors(assets, selectors["selectors"])
    candidates = resolved["initial_order_candidate_universe"]
    limit = int(os.getenv("LIVE_PRICE_E2E_LIMIT", "3"))
    candidates = candidates[:limit]
    assert candidates, "stage=resolve reason=no initial candidates"

    provider = get_default_price_provider(read_only=True)
    conn = sqlite3.connect(tmp_path / "market_data_e2e.db")
    conn.row_factory = sqlite3.Row

    failures = []
    for asset in candidates:
        prefix = f"{asset['asset_id']} {asset['symbol']} {asset['name']} {asset['market']} provider={provider.provider_name}"
        try:
            quote = provider.get_current_price(symbol=asset["symbol"], market=asset["market"])
        except Exception as exc:
            failures.append(f"{prefix} stage=query reason={type(exc).__name__}: {exc}")
            continue

        if Decimal(str(quote.price)) <= 0:
            failures.append(f"{prefix} stage=query reason=non-positive price={quote.price}")
            continue

        try:
            save_price_quote(asset=asset, quote=quote, db_session=conn)
        except Exception as exc:
            failures.append(f"{prefix} stage=save reason={type(exc).__name__}: {exc}")
            continue

        saved = get_latest_price_quote(symbol=asset["symbol"], market=asset["market"], db_session=conn)
        if saved is None:
            failures.append(f"{prefix} stage=read reason=no saved quote")
            continue
        if saved.price <= 0:
            failures.append(f"{prefix} stage=validate reason=non-positive db price={saved.price}")
        if saved.symbol != quote.symbol or saved.market != quote.market or saved.provider != quote.provider:
            failures.append(f"{prefix} stage=validate reason=symbol/market/provider mismatch")

    assert not failures, "\n".join(failures)
