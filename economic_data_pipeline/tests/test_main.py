# tests/test_main.py
# main.py의 safe_store 단위 테스트 (TODAY_ISO 제거 검증 포함)
import os
import tempfile
import sqlite3
import pytest
from datetime import date
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import init_db, get_previous_value


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


class TestSafeStore:
    """safe_store 함수의 핵심 동작 검증"""

    def _patch_db(self, monkeypatch, tmp_path):
        """safe_store가 tmp_db를 사용하도록 패치"""
        import main as m
        monkeypatch.setattr(m, "DB_PATH", tmp_path)

    def test_success_stores_value(self, tmp_db, monkeypatch):
        import main as m
        from database import get_latest
        monkeypatch.setattr(m, "DB_PATH", tmp_db)
        m.safe_store("TEST_IND", 99.9, "src", "unit", frequency="daily")
        df = get_latest("TEST_IND", n=5, db_path=tmp_db)
        assert len(df) == 1
        assert float(df.iloc[0]["value"]) == pytest.approx(99.9)

    def test_stale_flag_on_fallback(self, tmp_db, monkeypatch):
        import main as m
        monkeypatch.setattr(m, "DB_PATH", tmp_db)

        # 먼저 과거 값을 DB에 넣어둠
        from database import upsert_indicator
        upsert_indicator("2026-01-01", "TEST_IND", 50.0, "src", "unit", db_path=tmp_db)

        # value=None → 전일값 대체 → is_stale=1
        m.safe_store("TEST_IND", None, "src", "unit", frequency="daily")

        conn = sqlite3.connect(tmp_db)
        rows = conn.execute(
            "SELECT date, value, is_stale FROM indicators WHERE indicator='TEST_IND' ORDER BY date DESC"
        ).fetchall()
        conn.close()
        # 최신 레코드가 stale 표시
        assert rows[0][2] == 1

    def test_date_computed_freshly(self, tmp_db, monkeypatch):
        """TODAY_ISO 전역 상수가 없고 매번 date.today() 계산됨을 확인"""
        import main as m
        # main 모듈에 TODAY_ISO 상수가 없어야 함
        assert not hasattr(m, "TODAY_ISO"), \
            "TODAY_ISO 전역 상수가 main.py에 남아 있습니다!"

    def test_explicit_date_str_used(self, tmp_db, monkeypatch):
        import main as m
        monkeypatch.setattr(m, "DB_PATH", tmp_db)
        m.safe_store("CPI", 119.5, "ECOS", "index", date_str="2025-12-31", frequency="monthly")
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT date FROM indicators WHERE indicator='CPI'"
        ).fetchone()
        conn.close()
        assert row[0] == "2025-12-31"

    def test_none_value_no_fallback_no_store(self, tmp_db, monkeypatch):
        """전일값도 없을 때는 아무것도 저장되지 않아야 함"""
        import main as m
        monkeypatch.setattr(m, "DB_PATH", tmp_db)
        m.safe_store("EMPTY_IND", None, "src", "unit")
        conn = sqlite3.connect(tmp_db)
        count = conn.execute(
            "SELECT COUNT(*) FROM indicators WHERE indicator='EMPTY_IND'"
        ).fetchone()[0]
        conn.close()
        assert count == 0
