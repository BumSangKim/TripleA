import sqlite3
from datetime import date, timedelta

from api.macro_indicator_collector import collect_indicator_history, resolve_indicator_meta
from api.features.macro.repository import MacroRepository


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
            frequency TEXT,
            UNIQUE(date, indicator)
        )
        """
    )
    return conn


def _insert_indicator(
    conn: sqlite3.Connection,
    indicator: str,
    value_date: date,
    value: float,
    source: str = "test",
    unit: str = "pt",
    frequency: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO indicators
        (date, indicator, value, source, unit, frequency)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (value_date.isoformat(), indicator, value, source, unit, frequency),
    )
    conn.commit()


def test_get_indicator_history_collects_when_local_data_is_missing(monkeypatch):
    conn = _indicator_conn()
    today = date.today()
    calls = []

    def fake_collect(conn_arg, indicator, start, end):
        calls.append((indicator, start, end))
        _insert_indicator(conn_arg, indicator, today, 18.5, unit="B USD")
        return 1

    monkeypatch.setattr("api.macro_indicator_collector.collect_indicator_history", fake_collect)

    history = MacroRepository(conn).get_indicator_history("CAPEX_MSFT", days=30)

    assert calls
    assert history == [{"date": today.isoformat(), "value": 18.5}]


def test_get_indicator_history_uses_sparse_recent_data_without_refetch(monkeypatch):
    conn = _indicator_conn()
    recent_quarter = date.today() - timedelta(days=60)
    _insert_indicator(conn, "CAPEX_MSFT", recent_quarter, 18.5, unit="B USD")

    def fail_collect(*_args):
        raise AssertionError("fresh sparse quarterly data should not be refetched")

    monkeypatch.setattr("api.macro_indicator_collector.collect_indicator_history", fail_collect)

    history = MacroRepository(conn).get_indicator_history("CAPEX_MSFT", days=7)

    assert history == [{"date": recent_quarter.isoformat(), "value": 18.5}]


def test_get_indicator_history_fetches_when_range_not_covered(monkeypatch):
    conn = _indicator_conn()
    today = date.today()
    for months_back in range(1, 13):
        _insert_indicator(conn, "KOSPI", today - timedelta(days=months_back * 30), 2500 + months_back * 10)

    collect_calls = []

    def fake_collect(conn_arg, indicator, start, end):
        collect_calls.append((indicator, start, end))
        _insert_indicator(conn_arg, indicator, today - timedelta(days=365 * 3), 2000.0)
        return 1

    monkeypatch.setattr("api.macro_indicator_collector.collect_indicator_history", fake_collect)

    history = MacroRepository(conn).get_indicator_history("KOSPI", days=365 * 3)

    assert collect_calls
    assert any(item["date"] <= (today - timedelta(days=365 * 2)).isoformat() for item in history)


def test_get_indicator_history_no_collection_when_range_is_covered(monkeypatch):
    conn = _indicator_conn()
    today = date.today()
    for years_back in range(1, 5):
        _insert_indicator(conn, "KOSPI", today - timedelta(days=years_back * 365), 2500 + years_back * 100)
    _insert_indicator(conn, "KOSPI", today, 2600.0)

    def fail_collect(*_args):
        raise AssertionError("should not re-collect when range is already covered and data is fresh")

    monkeypatch.setattr("api.macro_indicator_collector.collect_indicator_history", fail_collect)

    assert MacroRepository(conn).get_indicator_history("KOSPI", days=365 * 3)


def test_resolve_indicator_meta_infers_fred_source():
    conn = _indicator_conn()
    _insert_indicator(
        conn,
        "DXY_FRED",
        date.today() - timedelta(days=10),
        119.2,
        source="FRED:DTWEXBGS",
        unit="pt",
    )

    meta = resolve_indicator_meta(conn, "DXY_FRED")

    assert meta
    assert meta["source_type"] == "fred"
    assert meta["symbol"] == "DTWEXBGS"


def test_fmp_capex_collector_saves_quarterly_rows(monkeypatch):
    conn = _indicator_conn()

    class FakeResponse:
        status_code = 200

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
