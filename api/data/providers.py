from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from api.data.models import CurrentQuote, MacroObservation, PriceBar


class DataProviderError(RuntimeError):
    pass


class DataProvider(Protocol):
    provider_name: str

    def get_price_history(self, symbols: list[str], start_date: date, end_date: date) -> list[PriceBar]:
        ...

    def get_current_quotes(self, symbols: list[str]) -> list[CurrentQuote]:
        ...

    def get_macro_indicators(
        self,
        indicator_keys: list[str],
        start_date: date,
        end_date: date,
    ) -> list[MacroObservation]:
        ...


class MockMarketDataProvider:
    provider_name = "mock"

    def __init__(self, *, fail_symbols: set[str] | None = None, empty: bool = False):
        self.fail_symbols = fail_symbols or set()
        self.empty = empty

    def get_price_history(self, symbols: list[str], start_date: date, end_date: date) -> list[PriceBar]:
        if self.empty:
            return []
        rows: list[PriceBar] = []
        now = datetime.now(UTC)
        for symbol in symbols:
            if symbol in self.fail_symbols:
                raise DataProviderError(f"mock provider failed for {symbol}")
            current = start_date
            offset = 0
            while current <= end_date:
                price = Decimal("100") + Decimal(offset)
                rows.append(
                    PriceBar(
                        symbol=symbol,
                        market="KRX",
                        date=current,
                        open=price,
                        high=price + Decimal("1"),
                        low=price - Decimal("1"),
                        close=price,
                        volume=Decimal("1000"),
                        source=self.provider_name,
                        as_of_date=end_date,
                        updated_at=now,
                    )
                )
                current += timedelta(days=1)
                offset += 1
        return rows

    def get_current_quotes(self, symbols: list[str]) -> list[CurrentQuote]:
        if self.empty:
            return []
        now = datetime.now(UTC)
        quotes: list[CurrentQuote] = []
        for index, symbol in enumerate(symbols):
            if symbol in self.fail_symbols:
                raise DataProviderError(f"mock provider failed for {symbol}")
            quotes.append(
                CurrentQuote(
                    symbol=symbol,
                    market="KRX",
                    price=Decimal("10000") + Decimal(index),
                    currency="KRW",
                    quote_time=now,
                    source=self.provider_name,
                    as_of_date=now.date(),
                    updated_at=now,
                )
            )
        return quotes


class MockMacroDataProvider:
    provider_name = "mock"

    def __init__(self, *, empty: bool = False):
        self.empty = empty

    def get_macro_indicators(
        self,
        indicator_keys: list[str],
        start_date: date,
        end_date: date,
    ) -> list[MacroObservation]:
        if self.empty:
            return []
        now = datetime.now(UTC)
        rows: list[MacroObservation] = []
        for index, indicator in enumerate(indicator_keys):
            rows.append(
                MacroObservation(
                    indicator_key=indicator,
                    date=start_date,
                    value=Decimal("3.0") + Decimal(index) / Decimal("10"),
                    unit="%",
                    source=self.provider_name,
                    as_of_date=end_date,
                    release_date=start_date + timedelta(days=30),
                    updated_at=now,
                )
            )
        return rows


class FailingProvider:
    provider_name = "failing"

    def get_price_history(self, symbols: list[str], start_date: date, end_date: date) -> list[PriceBar]:
        raise DataProviderError("provider unavailable")

    def get_current_quotes(self, symbols: list[str]) -> list[CurrentQuote]:
        raise DataProviderError("provider unavailable")

    def get_macro_indicators(self, indicator_keys: list[str], start_date: date, end_date: date) -> list[MacroObservation]:
        raise DataProviderError("provider unavailable")


def get_mock_provider(source_type: str):
    if source_type in {"macro", "fx", "interest_rate", "export_import"}:
        return MockMacroDataProvider()
    return MockMarketDataProvider()
