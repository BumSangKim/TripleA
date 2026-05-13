# tests/test_monitor.py
# monitor 모듈 단위 테스트
import os
import sqlite3
import tempfile
import pytest
from datetime import date, timedelta
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import init_db, upsert_indicator
from monitor import check_data_quality, get_stale_days


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


# ── get_stale_days ───────────────────────────────────────────────────────────

class TestGetStaleDays:
    def test_yaml_stale_days_used(self):
        meta = {"KOSPI": {"stale_days": 3, "frequency": "daily"}}
        assert get_stale_days("KOSPI", meta) == 3

    def test_frequency_fallback(self):
        meta = {"CPI": {"frequency": "monthly"}}
        assert get_stale_days("CPI", meta) == 40

    def test_quarterly_fallback(self):
        meta = {"GDP_GROWTH": {"frequency": "quarterly"}}
        assert get_stale_days("GDP_GROWTH", meta) == 100

    def test_unknown_indicator_daily_default(self):
        meta = {}
        assert get_stale_days("UNKNOWN_IND", meta) == 3


# ── check_data_quality ───────────────────────────────────────────────────────

class TestCheckDataQuality:
    def _populate(self, db_path, indicator, days_ago=0):
        d = (date.today() - timedelta(days=days_ago)).isoformat()
        upsert_indicator(d, indicator, 100.0, "test", "", db_path=db_path)

    def test_fresh_indicator_counts(self, tmp_db):
        self._populate(tmp_db, "KOSPI", days_ago=0)
        # Mock YAML to only track KOSPI
        fake_meta = {"KOSPI": {"stale_days": 3, "frequency": "daily", "layer": "korea"}}
        with patch("monitor._load_indicator_meta", return_value=fake_meta):
            quality = check_data_quality(db_path=tmp_db)
        assert quality["fresh_count"] == 1
        assert quality["completeness"] == 100.0

    def test_stale_indicator_not_counted(self, tmp_db):
        self._populate(tmp_db, "CPI", days_ago=50)  # 50일 전, monthly stale=40
        fake_meta = {"CPI": {"stale_days": 40, "frequency": "monthly", "layer": "korea"}}
        with patch("monitor._load_indicator_meta", return_value=fake_meta):
            quality = check_data_quality(db_path=tmp_db)
        assert quality["fresh_count"] == 0
        assert "CPI" in quality["stale_indicators"]

    def test_completeness_mixed(self, tmp_db):
        self._populate(tmp_db, "KOSPI", days_ago=0)   # fresh
        self._populate(tmp_db, "CPI", days_ago=50)    # stale (>40 days)
        fake_meta = {
            "KOSPI": {"stale_days": 3, "frequency": "daily", "layer": "korea"},
            "CPI":   {"stale_days": 40, "frequency": "monthly", "layer": "korea"},
        }
        with patch("monitor._load_indicator_meta", return_value=fake_meta):
            quality = check_data_quality(db_path=tmp_db)
        assert quality["fresh_count"] == 1
        assert quality["total_tracked"] == 2
        assert quality["completeness"] == 50.0


# ── alert_if_fail (기본 동작 확인) ───────────────────────────────────────────

class TestAlertIfFail:
    def test_no_alert_when_all_fresh(self, tmp_db):
        d = date.today().isoformat()
        upsert_indicator(d, "KOSPI", 7000.0, "test", "", db_path=tmp_db)
        fake_meta = {"KOSPI": {"stale_days": 3, "frequency": "daily", "layer": "korea"}}
        with patch("monitor._load_indicator_meta", return_value=fake_meta), \
             patch("monitor.requests.post") as mock_post:
            from monitor import alert_if_fail
            alert_if_fail(db_path=tmp_db)
            # 완전성 100% → 알림 전송 없음
            mock_post.assert_not_called()
