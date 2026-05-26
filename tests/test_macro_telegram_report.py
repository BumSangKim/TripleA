import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from api.macro_telegram_report import build_daily_macro_report_text, send_daily_macro_report
from api.telegram_service import load_telegram_config


def _report_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            indicator TEXT NOT NULL,
            value REAL,
            source TEXT,
            unit TEXT,
            updated TEXT,
            UNIQUE(date, indicator)
        );
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            market_value REAL,
            profit REAL
        );
        CREATE TABLE notification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_type TEXT NOT NULL,
            alert_type TEXT,
            message TEXT,
            dedup_key TEXT,
            status TEXT,
            sent_at TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    conn.executemany(
        "INSERT INTO indicators (date, indicator, value, source, unit) VALUES (?, ?, ?, ?, ?)",
        [
            ("2026-05-25", "USD_KRW", 1513.1, "Yahoo:USDKRW=X", "원"),
            ("2026-05-24", "USD_KRW", 1517.2, "Yahoo:USDKRW=X", "원"),
            ("2026-05-26", "KOSPI", 4100.5, "Yahoo:^KS11", "pt"),
            ("2026-05-25", "KOSPI", 4075.0, "Yahoo:^KS11", "pt"),
            ("2026-05-22", "US10Y", 4.48, "FRED:DGS10", "%"),
            ("2026-05-21", "US10Y", 4.5, "FRED:DGS10", "%"),
        ],
    )
    conn.commit()
    return conn


def test_build_daily_macro_report_uses_current_macro_data():
    conn = _report_conn()
    text, count = build_daily_macro_report_text(
        conn,
        now=datetime(2026, 5, 26, 8, 30, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert count == 3
    assert "TripleA 금일 경제 현황 요약" in text
    assert "USD/KRW: 1,513.1원" in text
    assert "KOSPI: 4,100.5 pt" in text
    assert "US10Y" in text


def test_send_daily_macro_report_posts_once_and_dedupes(monkeypatch):
    conn = _report_conn()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1234")
    posted = []

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True, "result": {"message_id": 77}}

    class DummyRequests:
        @staticmethod
        def post(url, json, timeout):
            posted.append({"url": url, "json": json, "timeout": timeout})
            return DummyResponse()

    now = datetime(2026, 5, 26, 8, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    first = send_daily_macro_report(conn, now=now, requests_module=DummyRequests)
    second = send_daily_macro_report(conn, now=now, requests_module=DummyRequests)

    assert first.sent == 1
    assert first.message_id == 77
    assert second.sent == 0
    assert second.skipped == 1
    assert len(posted) == 1
    assert "USD/KRW" in posted[0]["json"]["text"]

    log = conn.execute(
        "SELECT alert_type, status, dedup_key FROM notification_logs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert log["alert_type"] == "MACRO_DAILY"
    assert log["status"] == "SENT"
    assert log["dedup_key"] == "telegram:macro-daily:2026-05-26"


def test_load_telegram_config_accepts_legacy_key_file(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    dotenv_path = tmp_path / ".env"
    key_file = tmp_path / "TELEGRAM_KEY"
    key_file.write_text("KEY=legacy-token\nCHAT_ID=5678\n", encoding="utf-8")

    config = load_telegram_config(dotenv_path=dotenv_path, key_file=key_file)

    assert config.bot_token == "legacy-token"
    assert config.chat_id == "5678"


def test_load_telegram_config_requires_chat_id(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    key_file = tmp_path / "TELEGRAM_KEY"
    key_file.write_text("KEY=legacy-token\n", encoding="utf-8")

    with pytest.raises(Exception, match="TELEGRAM_CHAT_ID"):
        load_telegram_config(dotenv_path=tmp_path / ".env", key_file=key_file)
