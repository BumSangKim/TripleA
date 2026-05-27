import sqlite3
from datetime import date

from api.data.ingestion import collect_macro_data
from api.data.repository import read_latest_data_quality, read_macro_observations
from api.data.source_registry import load_data_sources


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_mock_macro_provider_saves_release_and_as_of_metadata():
    conn = _conn()
    source = [source for source in load_data_sources() if source.source_id == "mock_macro_monthly"][0]

    result = collect_macro_data(
        source=source,
        start_date=date(2026, 4, 1),
        end_date=date(2026, 5, 27),
        db_session=conn,
    )
    rows = read_macro_observations(
        indicator_key=source.symbols_or_indicators[0],
        start_date="2026-01-01",
        end_date="2026-12-31",
        db_session=conn,
    )

    assert result.status == "success"
    assert rows[0]["release_date"] == "2026-05-01"
    assert rows[0]["as_of_date"] == "2026-05-27"


def test_monthly_macro_stale_quality_is_recorded():
    conn = _conn()
    source = [source for source in load_data_sources() if source.source_id == "mock_macro_monthly"][0]

    collect_macro_data(
        source=source,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 5, 27),
        db_session=conn,
    )
    quality = read_latest_data_quality(dataset_key=f"macro:{source.source_id}", db_session=conn)

    assert quality["is_stale"] is True
    assert "stale_data" in quality["warnings"]


def test_disabled_macro_source_is_not_run():
    conn = _conn()
    source = [source for source in load_data_sources() if source.source_id == "fred_disabled_without_secret"][0]

    result = collect_macro_data(
        source=source,
        start_date=date(2026, 4, 1),
        end_date=date(2026, 5, 27),
        db_session=conn,
    )

    assert result.status == "skipped"
    assert result.row_count == 0
