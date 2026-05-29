from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from api.features.intraday.config import IntradayMonitoringConfig
from api.features.intraday.models import IntradayPriceSnapshot, ensure_aware
from api.features.intraday.universe import IntradaySymbol
from api.market_data.price_provider import PriceProvider, get_default_price_provider


class IntradayProviderError(RuntimeError):
    pass


class IntradaySnapshotProvider(Protocol):
    provider_name: str

    def fetch_snapshot(
        self,
        symbol: IntradaySymbol,
        *,
        captured_at: datetime,
        config: IntradayMonitoringConfig,
    ) -> IntradayPriceSnapshot:
        ...


class CurrentPriceIntradayProvider:
    provider_name = "current_price"

    def __init__(self, price_provider: PriceProvider | None = None):
        self.price_provider = price_provider or get_default_price_provider(read_only=True)

    def fetch_snapshot(
        self,
        symbol: IntradaySymbol,
        *,
        captured_at: datetime,
        config: IntradayMonitoringConfig,
    ) -> IntradayPriceSnapshot:
        quote = self.price_provider.get_current_price(symbol=symbol.symbol, market=symbol.market)
        quote_time = ensure_aware(quote.as_of or captured_at)
        stale_seconds = abs((ensure_aware(captured_at) - quote_time).total_seconds())
        is_stale = stale_seconds > config.stale_data_tolerance_seconds
        return IntradayPriceSnapshot(
            symbol=quote.symbol,
            market=quote.market,
            captured_at=quote_time,
            price=quote.price,
            source=quote.provider,
            quality_score=0.5 if is_stale else 0.8,
            is_stale=is_stale,
            raw_payload=quote.raw,
        )


class MockIntradayProvider:
    provider_name = "mock"

    def __init__(
        self,
        *,
        fail_symbols: set[str] | None = None,
        stale_symbols: set[str] | None = None,
        invalid_symbols: set[str] | None = None,
    ):
        self.fail_symbols = fail_symbols or set()
        self.stale_symbols = stale_symbols or set()
        self.invalid_symbols = invalid_symbols or set()
        self.requested: list[str] = []

    def fetch_snapshot(
        self,
        symbol: IntradaySymbol,
        *,
        captured_at: datetime,
        config: IntradayMonitoringConfig,
    ) -> IntradayPriceSnapshot:
        self.requested.append(symbol.symbol)
        if symbol.symbol in self.fail_symbols:
            raise IntradayProviderError(f"mock provider failed for {symbol.symbol}")
        effective_at = ensure_aware(captured_at)
        if symbol.symbol in self.stale_symbols:
            effective_at = effective_at - timedelta(seconds=config.stale_data_tolerance_seconds + 1)
        price = Decimal("0") if symbol.symbol in self.invalid_symbols else Decimal("100")
        return IntradayPriceSnapshot(
            symbol=symbol.symbol,
            market=symbol.market,
            captured_at=effective_at,
            price=price,
            open_price=Decimal("99"),
            high_price=Decimal("101"),
            low_price=Decimal("98"),
            volume=Decimal("1000"),
            value_traded=Decimal("100000"),
            change_rate=Decimal("1.0"),
            source=self.provider_name,
            quality_score=0.5 if symbol.symbol in self.stale_symbols else 1.0,
            is_stale=symbol.symbol in self.stale_symbols,
            raw_payload={"source": "mock"},
        )


def get_intraday_provider(config: IntradayMonitoringConfig) -> IntradaySnapshotProvider:
    if config.provider == "mock":
        return MockIntradayProvider()
    return CurrentPriceIntradayProvider()
