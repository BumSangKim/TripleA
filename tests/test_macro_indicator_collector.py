import sqlite3
from datetime import date, timedelta

from api.macro_indicator_collector import collect_indicator_history
from api.services import get_indicator_history


def _indicator_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
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
        )
        """
    )
    return conn


def test_get_indicator_history_collects_when_local_range_is_missing(monkeypatch):
    conn = _indicator_conn()
    today = date.today()
    calls = []

    def fake_collect(conn_arg, indicator, start, end):
        calls.append((indicator, start, end))
        conn_arg.execute(
            "INSERT INTO indicators (date, indicator, value, source, unit) VALUES (?, ?, ?, ?, ?)",
            (today.isoformat(), indicator, 18.5, "test", "B USD"),
        )
        conn_arg.commit()
        return 1

    monkeypatch.setattr("api.services.collect_indicator_history", fake_collect)

    history = get_indicator_history(conn, "CAPEX_MSFT", days=30)

    assert calls
    assert history == [{"date": today.isoformat(), "value": 18.5}]


def test_get_indicator_history_uses_sparse_recent_data_without_refetch(monkeypatch):
    conn = _indicator_conn()
    today = date.today()
    recent_quarter = today - timedelta(days=60)
    conn.execute(
        "INSERT INTO indicators (date, indicator, value, source, unit) VALUES (?, ?, ?, ?, ?)",
        (recent_quarter.isoformat(), "CAPEX_MSFT", 18.5, "test", "B USD"),
    )
    conn.commit()

    def fail_collect(*_args):
        raise AssertionError("fresh sparse quarterly data should not be refetched")

    monkeypatch.setattr("api.services.collect_indicator_history", fail_collect)

    history = get_indicator_history(conn, "CAPEX_MSFT", days=30)

    assert history == [{"date": recent_quarter.isoformat(), "value": 18.5}]


def test_fmp_capex_collector_saves_quarterly_rows(monkeypatch):
    conn = _indicator_conn()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"date": "2026-03-31", "capitalExpenditure": -30_876_000_000},
                {"date": "2025-12-31", "capitalExpenditure": -29_876_000_000},
                {"date": "2020-12-31", "capitalExpenditure": -1_000_000_000},
            ]

    request_args = {}

    def fake_get(url, params, timeout):
        request_args.update({"url": url, "params": params, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setattr("requests.get", fake_get)

    saved = collect_indicator_history(conn, "CAPEX_MSFT", date(2025, 1, 1), date(2026, 12, 31))

    rows = conn.execute("SELECT date, indicator, value, source, unit FROM indicators ORDER BY date").fetchall()
    assert saved == 2
    assert request_args["params"]["apikey"] == "test-key"
    assert [(r["date"], r["indicator"], r["value"], r["source"], r["unit"]) for r in rows] == [
        ("2025-12-31", "CAPEX_MSFT", 29.876, "FMP:MSFT", "B USD"),
        ("2026-03-31", "CAPEX_MSFT", 30.876, "FMP:MSFT", "B USD"),
    ]
