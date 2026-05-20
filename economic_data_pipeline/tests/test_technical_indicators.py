# tests/test_technical_indicators.py
# transforms/technical_indicators.py 단위 테스트
import os
import sys
import tempfile
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import init_db, upsert_indicator
from transforms.technical_indicators import (
    compute_sma,
    compute_ema,
    compute_rsi,
    compute_macd,
    compute_bollinger_bands,
    compute_all_features,
)


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


def _insert_prices(db_path, indicator, prices):
    """지정 가격 목록을 날짜순으로 DB에 삽입."""
    base = date(2024, 1, 1)
    for i, p in enumerate(prices):
        d = (base + timedelta(days=i)).isoformat()
        upsert_indicator(d, indicator, p, "test", "", db_path=db_path)


class TestComputeSMA:
    def test_basic_sma(self, tmp_db):
        _insert_prices(tmp_db, "TEST", [10, 20, 30, 40, 50])
        sma = compute_sma("TEST", period=3, db_path=tmp_db)
        assert not sma.empty
        assert sma.iloc[-1] == pytest.approx(40.0)

    def test_insufficient_data_returns_empty(self, tmp_db):
        _insert_prices(tmp_db, "TEST2", [10, 20])
        sma = compute_sma("TEST2", period=5, db_path=tmp_db)
        assert sma.empty

    def test_unknown_indicator_returns_empty(self, tmp_db):
        sma = compute_sma("NOPE", period=5, db_path=tmp_db)
        assert sma.empty


class TestComputeEMA:
    def test_returns_series_same_length_as_input(self, tmp_db):
        prices = list(range(1, 31))
        _insert_prices(tmp_db, "EMA_TEST", prices)
        ema = compute_ema("EMA_TEST", period=12, db_path=tmp_db)
        assert not ema.empty
        assert len(ema) == len(prices)

    def test_ema_last_greater_than_mean_when_rising(self, tmp_db):
        prices = list(range(100, 130))
        _insert_prices(tmp_db, "EMA_RISE", prices)
        ema = compute_ema("EMA_RISE", period=10, db_path=tmp_db)
        avg = sum(prices) / len(prices)
        assert float(ema.iloc[-1]) > avg  # EMA trails upward trend


class TestComputeRSI:
    def test_rsi_range(self, tmp_db):
        import random
        random.seed(42)
        prices = [100 + random.gauss(0, 5) for _ in range(30)]
        _insert_prices(tmp_db, "RSI_TEST", prices)
        rsi = compute_rsi("RSI_TEST", period=14, db_path=tmp_db)
        assert not rsi.empty
        assert float(rsi.min()) >= 0.0
        assert float(rsi.max()) <= 100.0

    def test_rsi_all_up_near_100(self, tmp_db):
        prices = [float(i) for i in range(1, 25)]
        _insert_prices(tmp_db, "RSI_UP", prices)
        rsi = compute_rsi("RSI_UP", period=14, db_path=tmp_db)
        assert not rsi.empty
        assert float(rsi.iloc[-1]) > 90.0

    def test_rsi_all_down_near_0(self, tmp_db):
        prices = [float(25 - i) for i in range(25)]
        _insert_prices(tmp_db, "RSI_DOWN", prices)
        rsi = compute_rsi("RSI_DOWN", period=14, db_path=tmp_db)
        assert not rsi.empty
        assert float(rsi.iloc[-1]) < 10.0


class TestComputeMACD:
    def test_returns_three_series(self, tmp_db):
        prices = [100.0 + i * 0.5 for i in range(40)]
        _insert_prices(tmp_db, "MACD_TEST", prices)
        result = compute_macd("MACD_TEST", db_path=tmp_db)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result
        assert not result["macd"].empty

    def test_insufficient_data_returns_empty_dict(self, tmp_db):
        _insert_prices(tmp_db, "MACD_SMAL", [1.0, 2.0, 3.0])
        result = compute_macd("MACD_SMAL", db_path=tmp_db)
        assert result["macd"].empty

    def test_histogram_is_macd_minus_signal(self, tmp_db):
        import numpy as np
        prices = [100.0 + i * 0.3 for i in range(40)]
        _insert_prices(tmp_db, "MACD_HIST", prices)
        result = compute_macd("MACD_HIST", db_path=tmp_db)
        expected = result["macd"] - result["signal"]
        # Align indices before comparing
        common_idx = result["histogram"].index.intersection(expected.index)
        assert len(common_idx) > 0
        diff = (result["histogram"].loc[common_idx] - expected.loc[common_idx]).abs()
        assert float(diff.max()) < 1e-9


class TestComputeBollingerBands:
    def test_returns_four_bands(self, tmp_db):
        prices = [100.0 + i * 0.1 for i in range(30)]
        _insert_prices(tmp_db, "BB_TEST", prices)
        result = compute_bollinger_bands("BB_TEST", period=20, db_path=tmp_db)
        for key in ("upper", "middle", "lower", "bandwidth"):
            assert key in result
            assert not result[key].empty

    def test_upper_gt_middle_gt_lower(self, tmp_db):
        import random
        random.seed(7)
        prices = [100 + random.gauss(0, 3) for _ in range(30)]
        _insert_prices(tmp_db, "BB_ORDER", prices)
        bb = compute_bollinger_bands("BB_ORDER", period=20, db_path=tmp_db)
        u = float(bb["upper"].iloc[-1])
        m = float(bb["middle"].iloc[-1])
        lo = float(bb["lower"].iloc[-1])
        assert u > m > lo


class TestComputeAllFeatures:
    def test_returns_all_keys(self, tmp_db):
        import random
        random.seed(1)
        prices = [100 + random.gauss(0, 5) for _ in range(60)]
        _insert_prices(tmp_db, "FEAT_IND", prices)
        feat = compute_all_features("FEAT_IND", db_path=tmp_db)
        assert feat.get("indicator") == "FEAT_IND"
        for key in ("sma5", "sma20", "ema12", "rsi14", "macd", "macd_signal",
                    "macd_hist", "bb_upper", "bb_lower"):
            assert key in feat, f"키 누락: {key}"

    def test_empty_indicator_returns_empty_dict(self, tmp_db):
        feat = compute_all_features("UNKNOWN_IND", db_path=tmp_db)
        assert feat == {}

    def test_rsi_signal_classification(self, tmp_db):
        # 오래 상승 → RSI 높아짐 → OVERBOUGHT
        prices = [float(i) for i in range(1, 61)]
        _insert_prices(tmp_db, "RSI_OB", prices)
        feat = compute_all_features("RSI_OB", db_path=tmp_db)
        assert feat.get("rsi_signal") == "OVERBOUGHT"

    def test_ma_signal_golden_cross(self, tmp_db):
        # 최근 상승 → sma5 > sma20 → GOLDEN_CROSS
        prices = [100.0] * 15 + [100.0 + i * 2 for i in range(1, 16)]
        _insert_prices(tmp_db, "MA_GC", prices)
        feat = compute_all_features("MA_GC", db_path=tmp_db)
        assert feat.get("ma_signal") == "GOLDEN_CROSS"
