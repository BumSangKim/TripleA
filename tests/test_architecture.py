import pandas as pd

from ingestion.base import DataCollector, NewsArticle
from engine.execution.order_executor import OrderExecutor, OrderRequest
from engine.execution.broker import PaperBrokerClient
from engine.features.pipeline import calculate_features, preprocess_data
from engine.risk.manager import PositionLimit, RiskManager
from storage.database import init_db


class FakeMarketClient:
    def fetch_market_data(self, symbol: str, timeframe: str):
        return pd.DataFrame(
            {
                "date": ["2026-01-02", "2026-01-01"],
                "close": [102.0, 100.0],
                "symbol": [symbol, symbol],
                "timeframe": [timeframe, timeframe],
            }
        )


class FakeNewsClient:
    def fetch_news(self, query: str):
        return [NewsArticle(title=f"{query} headline", url="https://example.com", source="fake")]


def test_data_collector_facade_fetches_market_and_news():
    collector = DataCollector({"market": FakeMarketClient(), "news": FakeNewsClient()})
    market = collector.fetch_market_data("SPY", "1d")
    news = collector.fetch_news("AI")

    assert list(market["close"]) == [102.0, 100.0]
    assert news[0].title == "AI headline"


def test_feature_pipeline_adds_baseline_features():
    raw = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=25), "close": range(100, 125)})
    cleaned = preprocess_data(raw)
    features = calculate_features(cleaned)

    assert "sma5" in features.columns
    assert "sma20" in features.columns
    assert features["sma20"].notna().any()


def test_order_executor_applies_risk_and_records_order(tmp_path):
    db_path = str(tmp_path / "orders.db")
    init_db(db_path)
    risk = RiskManager({"SPY": PositionLimit(max_order_notional=1_000, max_position_notional=5_000)})
    executor = OrderExecutor(PaperBrokerClient(), risk, db_path=db_path)

    result = executor.place_order(OrderRequest(symbol="SPY", side="BUY", qty=10, price=250.0))

    assert result.status == "filled"
    assert result.qty == 4.0
    assert result.reason == "quantity adjusted by risk limit"

