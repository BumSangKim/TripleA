import sqlite3
from datetime import date

from api.macro_data_service import get_macro_snapshot


def test_macro_snapshot_uses_latest_indicator_on_or_before_as_of_date():
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
    conn.executemany(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?, ?, ?, ?, ?)",
        [
            ("VIXCLS", 18.0, "pt", "2024-01-02", "test"),
            ("VIXCLS", 40.0, "pt", "2024-01-10", "test"),
            ("ISM_PMI", 53.0, "pt", "2024-01-05", "test"),
        ],
    )

    snapshot = get_macro_snapshot(conn, date(2024, 1, 6))

    assert snapshot.get_value("VIXCLS") == 18.0
    assert snapshot.get_value("ISM_PMI") == 53.0
    assert snapshot.indicators["VIXCLS"].data_date == date(2024, 1, 2)


def test_macro_snapshot_returns_empty_when_table_is_missing():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    snapshot = get_macro_snapshot(conn, date(2024, 1, 6))

    assert snapshot.indicators == {}
