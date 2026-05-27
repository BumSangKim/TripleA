import os
from decimal import Decimal

import pytest

from api.market_data.price_provider import get_default_price_provider
from api.universe.loader import load_assets, load_universe_selectors
from api.universe.selector import resolve_all_selectors

pytestmark = [pytest.mark.integration, pytest.mark.live_price]


def test_initial_order_candidate_universe_live_price_query():
    if os.getenv("RUN_LIVE_PRICE_SMOKE") != "1":
        pytest.skip("Set RUN_LIVE_PRICE_SMOKE=1 to run live price smoke test")

    assets = load_assets("config/universe")
    selectors = load_universe_selectors("config/universe")
    resolved = resolve_all_selectors(assets, selectors["selectors"])

    candidates = [
        asset
        for asset in resolved["initial_order_candidate_universe"]
        if asset["asset_type"] == "ETF"
        and asset["market"] == "KRX"
        and asset["tradability"]["order_candidate"] is True
    ]
    assert candidates, "No initial ETF order candidates to query"

    provider = get_default_price_provider(read_only=True)
    failures = []
    for asset in candidates:
        try:
            quote = provider.get_current_price(symbol=asset["symbol"], market=asset["market"])
            price = Decimal(str(quote.price))
            if price <= 0:
                failures.append(
                    f"{asset['asset_id']} {asset['symbol']} {asset['name']} "
                    f"{asset['market']} provider={provider.provider_name}: non-positive price={price}"
                )
        except Exception as exc:
            failures.append(
                f"{asset['asset_id']} {asset['symbol']} {asset['name']} "
                f"{asset['market']} provider={provider.provider_name}: {type(exc).__name__}: {exc}"
            )

    assert not failures, "\n".join(failures)
