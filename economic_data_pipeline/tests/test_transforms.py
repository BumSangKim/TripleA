# tests/test_transforms.py
# transforms/relative_strength.py 단위 테스트
import os
import tempfile
import pytest
from datetime import date

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import init_db, upsert_indicator
from transforms.relative_strength import (
    compute_relative_strength,
    build_rs_summary,
)


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


class TestComputeRelativeStrength:
    def _insert(self, db_path, indicator, value, days_ago=0):
        from datetime import timedelta
        d = (date.today() - timedelta(days=days_ago)).isoformat()
        upsert_indicator(d, indicator, value, "test", "USD", db_path=db_path)

    def test_basic_ratio(self, tmp_db):
        self._insert(tmp_db, "SMH", 220.0)
        self._insert(tmp_db, "SPY", 550.0)
        rs = compute_relative_strength("SMH", "SPY", db_path=tmp_db)
        assert rs == pytest.approx(220.0 / 550.0, rel=1e-4)

    def test_missing_numerator_returns_none(self, tmp_db):
        self._insert(tmp_db, "SPY", 550.0)
        rs = compute_relative_strength("SMH", "SPY", db_path=tmp_db)
        assert rs is None

    def test_missing_denominator_returns_none(self, tmp_db):
        self._insert(tmp_db, "SMH", 220.0)
        rs = compute_relative_strength("SMH", "SPY", db_path=tmp_db)
        assert rs is None

    def test_zero_denominator_returns_none(self, tmp_db):
        self._insert(tmp_db, "SMH", 220.0)
        self._insert(tmp_db, "SPY", 0.0)
        rs = compute_relative_strength("SMH", "SPY", db_path=tmp_db)
        assert rs is None


class TestBuildRsSummary:
    def test_returns_expected_keys(self, tmp_db):
        upsert_indicator(date.today().isoformat(), "SMH", 220.0, "test", "USD", db_path=tmp_db)
        upsert_indicator(date.today().isoformat(), "SPY", 550.0, "test", "USD", db_path=tmp_db)
        upsert_indicator(date.today().isoformat(), "XLU", 70.0, "test", "USD", db_path=tmp_db)
        summary = build_rs_summary(db_path=tmp_db)
        assert "RS_SMH_SPY" in summary
        assert "RS_XLU_SPY" in summary

    def test_ratio_computed(self, tmp_db):
        upsert_indicator(date.today().isoformat(), "SMH", 220.0, "test", "USD", db_path=tmp_db)
        upsert_indicator(date.today().isoformat(), "SPY", 550.0, "test", "USD", db_path=tmp_db)
        upsert_indicator(date.today().isoformat(), "XLU", 70.0, "test", "USD", db_path=tmp_db)
        summary = build_rs_summary(db_path=tmp_db)
        smh_rs = summary["RS_SMH_SPY"]["ratio"]
        assert smh_rs == pytest.approx(220.0 / 550.0, rel=1e-4)
