import sqlite3
from datetime import date

import pytest

from api.data.backfill import run_backfill_for_test
from api.data.providers import FailingProvider
from api.data.repository import count_rows, list_latest_ingestion_runs


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_dry_run_does_not_write_rows():
    conn = _conn()

    result = run_backfill_for_test(
        conn=conn,
        dataset="prices",
        start=date(2026, 5, 26),
        end=date(2026, 5, 27),
        dry_run=True,
    )

    assert result[0].status == "dry_run"
    assert count_rows("raw_market_prices", conn) == 0


def test_price_backfill_is_idempotent():
    conn = _conn()

    for _ in range(2):
        run_backfill_for_test(conn=conn, dataset="prices", start=date(2026, 5, 26), end=date(2026, 5, 27))

    assert count_rows("raw_market_prices", conn) == 4


def test_macro_backfill_is_idempotent():
    conn = _conn()

    for _ in range(2):
        run_backfill_for_test(conn=conn, dataset="macro", start=date(2026, 4, 1), end=date(2026, 5, 27))

    assert count_rows("raw_macro_indicators", conn) == 2


def test_invalid_date_range_fails():
    with pytest.raises(ValueError):
        run_backfill_for_test(conn=_conn(), dataset="prices", start=date(2026, 5, 27), end=date(2026, 5, 26))


def test_provider_failure_records_failed_run_status():
    conn = _conn()

    result = run_backfill_for_test(
        conn=conn,
        dataset="prices",
        start=date(2026, 5, 26),
        end=date(2026, 5, 27),
        provider=FailingProvider(),
    )
    runs = list_latest_ingestion_runs(db_session=conn)

    assert result[0].status == "failed"
    assert runs[0]["status"] == "failed"
