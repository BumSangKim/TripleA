from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import date

from api.data.strategy_data_readers import SqliteMacroSnapshotReader
from api.score_pipeline.adapters.macro_distribution_adapter import MacroDistributionAdapter


def test_sqlite_macro_reader_to_distribution_adapter_excludes_future_rows():
    conn = _macro_conn()
    conn.executemany(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?, ?, ?, ?, ?)",
        [
            ("VIXCLS", 40.0, "pt", "2024-03-08", "known"),
            ("VIXCLS", 12.0, "pt", "2024-03-15", "future"),
            ("ISM_PMI", 44.0, "pt", "2024-03-08", "known"),
        ],
    )

    snapshot = SqliteMacroSnapshotReader(conn).read_macro_snapshot(date(2024, 3, 10))
    output = MacroDistributionAdapter().adapt(snapshot)

    assert snapshot.get_value("VIXCLS") == 40.0
    assert output.dominant_regime == "volatility_stress"
    assert round(sum(output.distribution.values()), 6) == 1.0
    assert all("future" not in str(reason.detail) for reason in output.reason_codes)


def test_distribution_adapter_output_is_review_only_contract():
    conn = _macro_conn()
    snapshot = SqliteMacroSnapshotReader(conn).read_macro_snapshot(date(2024, 3, 10))

    output = MacroDistributionAdapter().adapt(snapshot)
    payload = asdict(output)

    assert output.dominant_regime_explanation_only is True
    assert output.warnings[0].code == "MISSING_MACRO_INPUT_REVIEW_REQUIRED"
    assert {"order", "orders", "execution", "broker"}.isdisjoint(payload)


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
