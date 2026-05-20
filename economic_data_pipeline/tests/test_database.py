# tests/test_database.py
# database 모듈 단위 테스트
import os
import sqlite3
import tempfile
import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import (
    init_db,
    upsert_indicator,
    get_latest,
    get_previous_value,
    log_collect,
    is_report_sent_today,
    mark_report_sent,
    save_raw_observation,
    log_collector_run,
    upsert_economic_event,
    save_event_release,
    get_upcoming_events,
    mask_sensitive_data,
    save_ir_keyword_mentions,
)


@pytest.fixture
def tmp_db():
    """테스트용 임시 DB 경로"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


# ── upsert_indicator ────────────────────────────────────────────────────────

class TestUpsertIndicator:
    def test_insert_basic(self, tmp_db):
        upsert_indicator("2026-01-01", "KOSPI", 7000.0, "Yahoo:^KS11", "pt", db_path=tmp_db)
        df = get_latest("KOSPI", n=5, db_path=tmp_db)
        assert len(df) == 1
        assert float(df.iloc[0]["value"]) == pytest.approx(7000.0)

    def test_upsert_overwrites(self, tmp_db):
        upsert_indicator("2026-01-01", "KOSPI", 7000.0, "Yahoo", "pt", db_path=tmp_db)
        upsert_indicator("2026-01-01", "KOSPI", 7100.0, "Yahoo", "pt", db_path=tmp_db)
        df = get_latest("KOSPI", n=5, db_path=tmp_db)
        assert len(df) == 1
        assert float(df.iloc[0]["value"]) == pytest.approx(7100.0)

    def test_is_stale_stored(self, tmp_db):
        upsert_indicator("2026-01-01", "KOSPI", 7000.0, "Yahoo", "pt",
                         db_path=tmp_db, is_stale=1)
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT is_stale FROM indicators WHERE indicator='KOSPI'"
        ).fetchone()
        conn.close()
        assert row[0] == 1

    def test_frequency_stored(self, tmp_db):
        upsert_indicator("2026-01-01", "CPI", 119.0, "ECOS", "index",
                         db_path=tmp_db, frequency="monthly")
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT frequency FROM indicators WHERE indicator='CPI'"
        ).fetchone()
        conn.close()
        assert row[0] == "monthly"

    def test_returns_sorted_by_date(self, tmp_db):
        for d, v in [("2026-01-01", 1.0), ("2026-01-03", 3.0), ("2026-01-02", 2.0)]:
            upsert_indicator(d, "TEST", v, "src", "", db_path=tmp_db)
        df = get_latest("TEST", n=10, db_path=tmp_db)
        dates = df["date"].tolist()
        assert dates == sorted(dates)


# ── get_previous_value ──────────────────────────────────────────────────────

class TestGetPreviousValue:
    def test_returns_none_when_empty(self, tmp_db):
        assert get_previous_value("NONEXISTENT", db_path=tmp_db) is None

    def test_returns_latest(self, tmp_db):
        upsert_indicator("2026-01-01", "GOLD", 3000.0, "src", "", db_path=tmp_db)
        upsert_indicator("2026-01-02", "GOLD", 3100.0, "src", "", db_path=tmp_db)
        assert get_previous_value("GOLD", db_path=tmp_db) == pytest.approx(3100.0)


# ── report_runs ─────────────────────────────────────────────────────────────

class TestReportRuns:
    def test_not_sent_initially(self, tmp_db):
        assert is_report_sent_today(db_path=tmp_db) is False

    def test_mark_and_check(self, tmp_db):
        mark_report_sent(message_len=100, status="ok", db_path=tmp_db)
        assert is_report_sent_today(db_path=tmp_db) is True

    def test_fail_status_not_counted(self, tmp_db):
        mark_report_sent(message_len=0, status="fail", db_path=tmp_db)
        assert is_report_sent_today(db_path=tmp_db) is False


# ── raw_observations ────────────────────────────────────────────────────────

class TestRawObservations:
    def test_save_dict(self, tmp_db):
        save_raw_observation("FRED:CPIAUCSL", {"value": "330.29", "date": "2026-01-01"},
                             indicator="US_CPI", db_path=tmp_db)
        conn = sqlite3.connect(tmp_db)
        row = conn.execute("SELECT source, indicator FROM raw_observations").fetchone()
        conn.close()
        assert row[0] == "FRED:CPIAUCSL"
        assert row[1] == "US_CPI"

    def test_save_list(self, tmp_db):
        save_raw_observation("ECOS:KEY", [{"key": "val"}], db_path=tmp_db)
        conn = sqlite3.connect(tmp_db)
        count = conn.execute("SELECT COUNT(*) FROM raw_observations").fetchone()[0]
        conn.close()
        assert count == 1

    def test_masks_api_keys(self, tmp_db):
        save_raw_observation(
            "FRED:TEST",
            {
                "url": "https://example.com/data?api_key=SECRET&x=1",
                "params": {"apikey": "SECRET2", "series_id": "CPI"},
            },
            db_path=tmp_db,
        )
        conn = sqlite3.connect(tmp_db)
        raw_json = conn.execute("SELECT raw_json FROM raw_observations").fetchone()[0]
        conn.close()
        assert "SECRET" not in raw_json
        assert "SECRET2" not in raw_json
        assert "***MASKED***" in raw_json

    def test_mask_sensitive_data_helper(self):
        masked = mask_sensitive_data({"access_token": "abc", "nested": {"client_secret": "def"}})
        assert masked["access_token"] == "***MASKED***"
        assert masked["nested"]["client_secret"] == "***MASKED***"


# ── collector_runs ──────────────────────────────────────────────────────────

class TestCollectorRuns:
    def test_log_collector_run(self, tmp_db):
        log_collector_run(
            "ecos_keystat",
            "ok",
            items_ok=8,
            started_at="2026-01-01T00:00:00",
            finished_at="2026-01-01T00:00:01",
            db_path=tmp_db,
        )
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT collector, status, items_ok, finished_at FROM collector_runs"
        ).fetchone()
        conn.close()
        assert row[0] == "ecos_keystat"
        assert row[1] == "ok"
        assert row[2] == 8
        assert row[3] == "2026-01-01T00:00:01"


# ── economic_events ─────────────────────────────────────────────────────────

class TestEconomicEvents:
    def test_upsert_event(self, tmp_db):
        ev_id = upsert_economic_event("2026-06-01", "US_CPI", country="US", db_path=tmp_db)
        assert isinstance(ev_id, int)

    def test_upsert_idempotent(self, tmp_db):
        id1 = upsert_economic_event("2026-06-01", "NFP", db_path=tmp_db)
        id2 = upsert_economic_event("2026-06-01", "NFP", db_path=tmp_db)
        assert id1 == id2

    def test_save_event_release(self, tmp_db):
        ev_id = upsert_economic_event("2026-06-01", "US_CPI", db_path=tmp_db)
        save_event_release(ev_id, actual=330.0, forecast=329.5, revised=329.4, unit="index",
                           source="BLS", db_path=tmp_db)
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT actual, forecast, surprise, revised, interpretation FROM event_releases WHERE event_id=?",
            (ev_id,)
        ).fetchone()
        conn.close()
        assert row[0] == pytest.approx(330.0)
        assert row[2] == pytest.approx(0.5)
        assert row[3] == pytest.approx(329.4)
        assert row[4] == "hawkish"

    def test_unemployment_positive_surprise_is_dovish(self, tmp_db):
        ev_id = upsert_economic_event("2026-06-01", "Unemployment Rate", db_path=tmp_db)
        save_event_release(ev_id, actual=4.2, forecast=4.0, db_path=tmp_db)
        conn = sqlite3.connect(tmp_db)
        row = conn.execute(
            "SELECT surprise, interpretation FROM event_releases WHERE event_id=?",
            (ev_id,)
        ).fetchone()
        conn.close()
        assert row[0] == pytest.approx(0.2)
        assert row[1] == "dovish"

    def test_get_upcoming_events(self, tmp_db):
        upsert_economic_event("2099-12-31", "FOMC", db_path=tmp_db)
        events = get_upcoming_events(days_ahead=365 * 100, db_path=tmp_db)
        names = [e["event_name"] for e in events]
        assert "FOMC" in names


class TestIrKeywordMentions:
    def test_save_ir_keyword_mentions(self, tmp_db):
        filing = {"accession": "0001", "ticker": "NVDA", "date": "2026-01-01"}
        save_ir_keyword_mentions(filing, {"HBM": 3, "CoWoS": 1}, db_path=tmp_db)
        conn = sqlite3.connect(tmp_db)
        rows = conn.execute(
            "SELECT keyword, mention_count FROM ir_keyword_mentions WHERE ticker='NVDA' ORDER BY keyword"
        ).fetchall()
        conn.close()
        assert rows == [("CoWoS", 1), ("HBM", 3)]
