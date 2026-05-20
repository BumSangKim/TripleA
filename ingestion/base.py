"""Common data collection interfaces."""

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd


class APIClient(Protocol):
    """Protocol for exchange, broker, market-data, or crawler clients."""

    def get(self, *args: Any, **kwargs: Any) -> Any:
        ...


@dataclass(frozen=True)
class NewsArticle:
    title: str
    url: str
    source: str
    published_at: str | None = None
    summary: str | None = None


class DataCollector:
    """Facade over source-specific API clients."""

    def __init__(self, api_clients: dict[str, APIClient]):
        self.api_clients = api_clients

    def _client(self, name: str) -> APIClient:
        try:
            return self.api_clients[name]
        except KeyError as exc:
            raise KeyError(f"등록되지 않은 데이터 클라이언트: {name}") from exc

    def fetch_market_data(self, symbol: str, timeframe: str, client: str = "market") -> pd.DataFrame:
        source = self._client(client)
        if hasattr(source, "fetch_market_data"):
            return source.fetch_market_data(symbol=symbol, timeframe=timeframe)
        return source.get(symbol=symbol, timeframe=timeframe)

    def fetch_news(self, query: str, client: str = "news") -> list[NewsArticle]:
        source = self._client(client)
        if hasattr(source, "fetch_news"):
            return source.fetch_news(query=query)
        rows = source.get(query=query)
        return [NewsArticle(**row) if isinstance(row, dict) else row for row in rows]

