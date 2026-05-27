from datetime import date

import pytest

from api.data.providers import DataProviderError, FailingProvider, MockMacroDataProvider, MockMarketDataProvider


def test_mock_market_provider_returns_typed_price_history_with_as_of_date():
    provider = MockMarketDataProvider()

    rows = provider.get_price_history(["360750"], date(2026, 5, 26), date(2026, 5, 27))

    assert len(rows) == 2
    assert rows[0].symbol == "360750"
    assert rows[0].as_of_date == date(2026, 5, 27)
    assert rows[0].updated_at is not None


def test_mock_market_provider_returns_current_quotes():
    quote = MockMarketDataProvider().get_current_quotes(["360750"])[0]

    assert quote.price > 0
    assert quote.as_of_date is not None
    assert quote.source == "mock"


def test_mock_macro_provider_returns_release_metadata():
    row = MockMacroDataProvider().get_macro_indicators(["CPIAUCSL"], date(2026, 4, 1), date(2026, 5, 27))[0]

    assert row.indicator_key == "CPIAUCSL"
    assert row.release_date is not None
    assert row.as_of_date == date(2026, 5, 27)


def test_empty_provider_result_is_explicit_empty_list():
    assert MockMarketDataProvider(empty=True).get_current_quotes(["360750"]) == []


def test_provider_failure_is_standardized():
    with pytest.raises(DataProviderError):
        FailingProvider().get_current_quotes(["360750"])
