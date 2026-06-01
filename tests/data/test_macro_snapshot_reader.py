from __future__ import annotations

import sqlite3
from datetime import date

from api.data.macro_snapshot_reader import get_macro_snapshot
from api.data.strategy_data_readers import SqliteMacroSnapshotReader


def test_macro_snapshot_uses_latest_indicator_on_or_before_as_of_date():
    conn = _macro_conn()
    conn.executemany(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?, ?, ?, ?, ?)",
        [
            ("VIXCLS", 18.0, "pt", "2024-01-02", "test"),
            ("VIXCLS", 40.0, "pt", "2024-01-10", "test"),
            ("VIXCLS", 99.0, "pt", "2024-01-20", "future"),
            ("ISM_PMI", 53.0, "pt", "2024-01-05", "test"),
        ],
    )

    snapshot = get_macro_snapshot(conn, date(2024, 1, 10))

    assert snapshot.get_value("VIXCLS") == 40.0
    assert snapshot.get_value("ISM_PMI") == 53.0
    assert snapshot.indicators["VIXCLS"].data_date == date(2024, 1, 10)
    assert snapshot.indicators["VIXCLS"].source == "test"


def test_macro_snapshot_excludes_future_rows():
    conn = _macro_conn()
    conn.executemany(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?, ?, ?, ?, ?)",
        [
            ("VIXCLS", 18.0, "pt", "2024-01-02", "known"),
            ("VIXCLS", 99.0, "pt", "2024-01-20", "future"),
        ],
    )

    snapshot = get_macro_snapshot(conn, date(2024, 1, 6))

    assert snapshot.get_value("VIXCLS") == 18.0
    assert snapshot.indicators["VIXCLS"].source == "known"


def test_macro_snapshot_returns_empty_when_table_is_missing():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    snapshot = get_macro_snapshot(conn, date(2024, 1, 6))

    assert snapshot.indicators == {}


def test_sqlite_macro_snapshot_reader_returns_strategy_input_model():
    conn = _macro_conn()
    conn.execute(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?, ?, ?, ?, ?)",
        ("VIXCLS", 18.0, "pt", "2024-01-02", "test"),
    )

    snapshot = SqliteMacroSnapshotReader(conn).read_macro_snapshot(date(2024, 1, 6))

    assert snapshot.as_of_date == date(2024, 1, 6)
    assert snapshot.indicators["VIXCLS"].indicator == "VIXCLS"
    assert snapshot.indicators["VIXCLS"].value == 18.0
    assert snapshot.indicators["VIXCLS"].data_date == date(2024, 1, 2)


def _macro_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator TEXT,
            value REAL,
            unit TEXT,
            date TEXT,
            source TEXT
        )
        """
    )
    return conn
