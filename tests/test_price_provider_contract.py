from decimal import Decimal

import pytest

from api.market_data.models import PriceQuote
from api.market_data.price_provider import (
    MockPriceProvider,
    UnsupportedProviderModeError,
    get_default_price_provider,
)


def test_price_quote_converts_price_to_decimal():
    quote = PriceQuote(
        symbol="360750",
        market="KRX",
        price="123.45",
        currency="KRW",
        provider="test",
    )

    assert quote.price == Decimal("123.45")


def test_mock_price_provider_returns_positive_quote():
    quote = MockPriceProvider().get_current_price(symbol="360750", market="KRX")

    assert quote.price > 0
    assert quote.currency == "KRW"
    assert quote.provider == "mock"


def test_default_provider_does_not_create_non_read_only_provider():
    with pytest.raises(UnsupportedProviderModeError):
        get_default_price_provider(read_only=False)


def test_provider_contract_does_not_expose_order_methods():
    provider = get_default_price_provider(read_only=True)

    for method_name in ("order", "place_order", "submit_order", "buy", "sell"):
        assert not hasattr(provider, method_name)
