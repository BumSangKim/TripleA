import sqlite3

from api.data.ingestion import check_current_quotes
from api.data.providers import DataProviderError, MockMarketDataProvider
from api.data.repository import list_latest_ingestion_runs, read_latest_quote
from api.data.source_registry import load_data_sources


class PartialFailingQuoteProvider(MockMarketDataProvider):
    def get_current_quotes(self, symbols):
        quotes = []
        for symbol in symbols:
            if symbol == symbols[-1]:
                raise DataProviderError(f"mock failure for {symbol}")
            quotes.extend(super().get_current_quotes([symbol]))
        return quotes


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _quote_source():
    return [source for source in load_data_sources() if source.source_id == "mock_current_quotes"][0]


def test_mock_current_quote_is_saved_and_read_back():
    conn = _conn()
    source = _quote_source()

    result = check_current_quotes(source=source, db_session=conn)
    quote = read_latest_quote(symbol=source.symbols_or_indicators[0], market="KRX", db_session=conn)

    assert result.status == "success"
    assert quote is not None
    assert quote["price"] > 0


def test_current_quote_failure_is_recorded_as_failed_run():
    conn = _conn()
    source = _quote_source()

    result = check_current_quotes(source=source, provider=PartialFailingQuoteProvider(), db_session=conn)
    runs = list_latest_ingestion_runs(db_session=conn)

    assert result.status == "failed"
    assert runs[0]["status"] == "failed"
    assert "mock failure" in runs[0]["error_message"]


def test_secretless_live_check_defaults_to_mock_safe_path(monkeypatch):
    monkeypatch.delenv("RUN_LIVE_PRICE_SMOKE", raising=False)

    result = check_current_quotes(source=_quote_source(), provider=MockMarketDataProvider(), db_session=_conn())

    assert result.status == "success"


def test_current_quote_cli_default_output_does_not_recreate_docs(tmp_path, monkeypatch):
    from api.data.check_current_quotes import main

    source = _quote_source()
    monkeypatch.setattr("api.data.check_current_quotes.load_data_sources", lambda: [source])
    monkeypatch.chdir(tmp_path)

    assert main([]) == 0
    assert (tmp_path / "data" / "PHASE_3_CURRENT_PRICE_CHECK.md").exists()
    assert not (tmp_path / "docs").exists()
