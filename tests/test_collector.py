# tests/test_collector.py
import json
import os
import sqlite3
import sys
import tempfile
import types

import pytest


from storage.database import init_db


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


class FakeResponse:
    def __init__(self, data=None, status_code=200, text="ok", content=b"data"):
        self._data = data if data is not None else {}
        self.status_code = status_code
        self.text = text
        self.content = content

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def _raw_rows(db_path):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT source, raw_json FROM raw_observations ORDER BY id").fetchall()
    conn.close()
    return rows


def test_fetch_ecos_keystat_saves_masked_raw(tmp_db, monkeypatch):
    import ingestion.collector as collector

    monkeypatch.setattr(collector, "ECOS_KEY", "ECOS_SECRET")
    response = FakeResponse({
        "KeyStatisticList": {
            "row": [{"KEYSTAT_NAME": "소비자물가지수", "DATA_VALUE": "120.1", "UNIT_NAME": "pt"}]
        }
    })
    monkeypatch.setattr(collector, "get_session", lambda: FakeSession(response))

    result = collector.fetch_ecos_keystat(db_path=tmp_db)

    assert result["소비자물가지수"]["value"] == pytest.approx(120.1)
    rows = _raw_rows(tmp_db)
    assert rows[0][0] == "ECOS:KeyStatisticList"
    assert "ECOS_SECRET" not in rows[0][1]
    assert "***MASKED***" in rows[0][1]


def test_fetch_fred_saves_masked_raw(tmp_db, monkeypatch):
    import ingestion.collector as collector

    monkeypatch.setattr(collector, "FRED_KEY", "FRED_SECRET")
    response = FakeResponse({"observations": [{"date": "2026-01-01", "value": "10"}]})
    monkeypatch.setattr(collector, "get_session", lambda: FakeSession(response))

    obs = collector.fetch_fred("DGS10", db_path=tmp_db)

    assert obs[0]["value"] == "10"
    raw = _raw_rows(tmp_db)[0][1]
    assert "FRED_SECRET" not in raw
    assert "***MASKED***" in raw


def test_fetch_yahoo_quote_saves_raw(tmp_db, monkeypatch):
    import ingestion.collector as collector

    response = FakeResponse({
        "chart": {
            "result": [{
                "meta": {"regularMarketPrice": 101.5, "regularMarketTime": 1767225600, "exchangeTimezoneName": "UTC"},
                "timestamp": [],
                "indicators": {"quote": [{"close": []}]},
            }]
        }
    })
    monkeypatch.setattr(collector, "get_session", lambda: FakeSession(response))

    result = collector.fetch_yahoo_quote("SPY", db_path=tmp_db)

    assert result[1] == pytest.approx(101.5)
    assert _raw_rows(tmp_db)[0][0] == "Yahoo:SPY"


def test_fetch_fmp_capex_saves_masked_raw(tmp_db, monkeypatch):
    import ingestion.collector as collector

    monkeypatch.setattr(collector, "FMP_KEY", "FMP_SECRET")
    response = FakeResponse([{"date": "2026-03-31", "capitalExpenditure": -1230000000}])
    monkeypatch.setattr(collector, "get_session", lambda: FakeSession(response))

    rows = collector.fetch_fmp_capex("NVDA", db_path=tmp_db)

    assert rows[0]["capex_b"] == pytest.approx(1.23)
    raw = _raw_rows(tmp_db)[0][1]
    assert "FMP_SECRET" not in raw
    assert "***MASKED***" in raw


def test_fetch_fmp_capex_402_uses_sec_fallback(tmp_db, monkeypatch):
    import ingestion.collector as collector

    monkeypatch.setattr(collector, "FMP_KEY", "FMP_SECRET")
    monkeypatch.setattr(collector, "get_session", lambda: FakeSession(FakeResponse({}, status_code=402)))
    monkeypatch.setattr(
        collector,
        "fetch_sec_capex",
        lambda ticker, limit=5, db_path=None: [{"date": "2026-03-31", "capex_b": 6.1, "ticker": ticker}],
    )

    rows = collector.fetch_fmp_capex("NEE", db_path=tmp_db)

    assert rows == [{"date": "2026-03-31", "capex_b": 6.1, "ticker": "NEE"}]


def test_fetch_nyfed_gscpi_saves_raw(tmp_db, monkeypatch):
    import ingestion.collector as collector

    class FakeCell:
        def __init__(self, value):
            self.value = value

    class FakeSheet:
        nrows = 2

        def cell(self, row, col):
            values = {(1, 0): "2026-01", (1, 1): 0.42}
            return FakeCell(values[(row, col)])

    class FakeWorkbook:
        def sheet_by_name(self, name):
            assert name == "GSCPI Monthly Data"
            return FakeSheet()

    fake_xlrd = types.SimpleNamespace(open_workbook=lambda file_contents: FakeWorkbook())
    monkeypatch.setitem(sys.modules, "xlrd", fake_xlrd)
    monkeypatch.setattr(collector, "get_session", lambda: FakeSession(FakeResponse(content=b"xlsx")))

    val = collector.fetch_nyfed_pmi_sdt(db_path=tmp_db)

    assert val == pytest.approx(0.42)
    assert _raw_rows(tmp_db)[0][0] == "NY_FED:GSCPI"


def test_fetch_grid_intelligence_parses_load_and_margin(tmp_db, monkeypatch):
    import ingestion.collector as collector

    response = FakeResponse({
        "demand_mw": "1000",
        "demand_period": "2026-05-20T13",
        "generation_mix": {"NG": {"mw": "900"}, "WND": {"mw": "150"}},
        "region": "ERCOT",
    })
    monkeypatch.setattr(collector, "get_session", lambda: FakeSession(response))

    result = collector.fetch_grid_intelligence("ERCOT", db_path=tmp_db)

    assert result["load_mw"] == pytest.approx(1000)
    assert result["reserve_margin_pct"] == pytest.approx(5.0)
    assert _raw_rows(tmp_db)[0][0] == "DCHub:ERCOT"
