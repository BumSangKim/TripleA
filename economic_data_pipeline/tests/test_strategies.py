# tests/test_strategies.py
# strategies/ 패키지 단위 테스트
import os
import sys
import tempfile
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import init_db, upsert_indicator
from strategies.golden_cross import GoldenCrossStrategy
from strategies.rsi_signal import RSISignalStrategy
from strategies.macd_signal import MACDSignalStrategy
from strategies import run_all_strategies


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


def _insert_prices(db_path, indicator, prices):
    base = date(2024, 1, 1)
    for i, p in enumerate(prices):
        d = (base + timedelta(days=i)).isoformat()
        upsert_indicator(d, indicator, p, "test", "", db_path=db_path)


# ── GoldenCrossStrategy ────────────────────────────────────────────────────────

class TestGoldenCrossStrategy:
    def test_buy_on_golden_cross(self):
        features = {
            "indicator": "TEST",
            "latest": 110.0,
            "sma5": 110.0,
            "sma20": 100.0,
            "ma_signal": "GOLDEN_CROSS",
        }
        sig = GoldenCrossStrategy().generate(features)
        assert sig is not None
        assert sig["signal_type"] == "BUY"
        assert sig["indicator"] == "TEST"
        assert 0 < sig["confidence"] <= 1.0

    def test_sell_on_dead_cross(self):
        features = {
            "indicator": "TEST",
            "latest": 90.0,
            "sma5": 90.0,
            "sma20": 100.0,
            "ma_signal": "DEAD_CROSS",
        }
        sig = GoldenCrossStrategy().generate(features)
        assert sig is not None
        assert sig["signal_type"] == "SELL"

    def test_no_signal_when_ma_signal_missing(self):
        features = {"indicator": "TEST", "latest": 100.0, "sma5": None, "sma20": None}
        sig = GoldenCrossStrategy().generate(features)
        assert sig is None

    def test_confidence_grows_with_gap(self):
        small_gap = {"indicator": "A", "latest": 101.0, "sma5": 101.0, "sma20": 100.0, "ma_signal": "GOLDEN_CROSS"}
        large_gap = {"indicator": "A", "latest": 120.0, "sma5": 120.0, "sma20": 100.0, "ma_signal": "GOLDEN_CROSS"}
        sig_s = GoldenCrossStrategy().generate(small_gap)
        sig_l = GoldenCrossStrategy().generate(large_gap)
        assert sig_l["confidence"] > sig_s["confidence"]


# ── RSISignalStrategy ──────────────────────────────────────────────────────────

class TestRSISignalStrategy:
    def test_buy_when_oversold(self):
        features = {"indicator": "TEST", "latest": 50.0, "rsi14": 20.0}
        sig = RSISignalStrategy().generate(features)
        assert sig is not None
        assert sig["signal_type"] == "BUY"

    def test_sell_when_overbought(self):
        features = {"indicator": "TEST", "latest": 200.0, "rsi14": 80.0}
        sig = RSISignalStrategy().generate(features)
        assert sig is not None
        assert sig["signal_type"] == "SELL"

    def test_no_signal_when_neutral(self):
        for rsi in [30.0, 50.0, 70.0]:
            features = {"indicator": "TEST", "latest": 100.0, "rsi14": rsi}
            sig = RSISignalStrategy().generate(features)
            assert sig is None

    def test_no_signal_when_rsi_missing(self):
        features = {"indicator": "TEST", "latest": 100.0}
        sig = RSISignalStrategy().generate(features)
        assert sig is None

    def test_confidence_in_range(self):
        for rsi in [10.0, 25.0, 75.0, 90.0]:
            features = {"indicator": "X", "latest": 100.0, "rsi14": rsi}
            sig = RSISignalStrategy().generate(features)
            if sig:
                assert 0.5 <= sig["confidence"] <= 0.95


# ── MACDSignalStrategy ────────────────────────────────────────────────────────

class TestMACDSignalStrategy:
    def _feat(self, hist, bias, latest=100.0):
        return {
            "indicator": "X",
            "latest": latest,
            "macd_hist": hist,
            "macd_bias": bias,
            "macd": hist * 2,
        }

    def test_buy_bullish(self):
        sig = MACDSignalStrategy().generate(self._feat(5.0, "BULLISH", 100.0))
        assert sig is not None
        assert sig["signal_type"] == "BUY"

    def test_sell_bearish(self):
        sig = MACDSignalStrategy().generate(self._feat(-5.0, "BEARISH", 100.0))
        assert sig is not None
        assert sig["signal_type"] == "SELL"

    def test_no_signal_when_missing(self):
        sig = MACDSignalStrategy().generate({"indicator": "X", "latest": 100.0})
        assert sig is None

    def test_very_small_hist_no_signal(self):
        # histogram tiny relative to price → confidence below MIN_CONFIDENCE
        sig = MACDSignalStrategy().generate(self._feat(0.001, "BULLISH", 10000.0))
        assert sig is None


# ── run_all_strategies ────────────────────────────────────────────────────────

class TestRunAllStrategies:
    def test_returns_list(self, tmp_db):
        # 명확한 신호 만들기: 오랜 상승 → RSI overbought + golden cross
        prices = [float(i + 50) for i in range(60)]
        _insert_prices(tmp_db, "KOSPI", prices)
        result = run_all_strategies(indicators=["KOSPI"], db_path=tmp_db)
        assert isinstance(result, list)

    def test_unknown_indicator_returns_empty(self, tmp_db):
        result = run_all_strategies(indicators=["UNKNOWN_XYZ"], db_path=tmp_db)
        assert result == []

    def test_signal_schema(self, tmp_db):
        prices = [float(i + 50) for i in range(60)]
        _insert_prices(tmp_db, "GOLD", prices)
        result = run_all_strategies(indicators=["GOLD"], db_path=tmp_db)
        for sig in result:
            assert "indicator" in sig
            assert "signal_type" in sig
            assert "strategy" in sig
            assert "confidence" in sig
            assert sig["signal_type"] in ("BUY", "SELL", "HOLD")
