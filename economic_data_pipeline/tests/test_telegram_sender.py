# tests/test_telegram_sender.py
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import init_db, mark_report_sent


@pytest.fixture
def tmp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


def _patch_report_dependencies(monkeypatch):
    import telegram_sender as ts

    calls = []
    monkeypatch.setattr(ts, "_tg_send_message", lambda text, parse_mode="Markdown": calls.append(text) or True)
    monkeypatch.setattr(ts, "_tg_send_photo", lambda *args, **kwargs: True)
    monkeypatch.setattr(ts, "_tg_send_document", lambda *args, **kwargs: True)
    monkeypatch.setattr(ts, "create_multi_chart", lambda *args, **kwargs: None)
    monkeypatch.setattr(ts, "create_capex_chart", lambda *args, **kwargs: None)
    monkeypatch.setattr(ts, "_send_csv", lambda *args, **kwargs: None)
    monkeypatch.setattr(ts, "build_summary", lambda db_path: {
        "US10Y": {"label": "미국 10Y", "latest": 4.3, "unit": "%", "change_pct": 0.1},
        "DXY": {"label": "DXY", "latest": 102.0, "unit": "index", "change_pct": -0.1},
    })
    monkeypatch.setattr(ts, "build_equity_summary", lambda db_path: {
        "SMH": {"label": "SMH", "latest": 250.0, "unit": "USD", "change_pct": 1.0},
        "XLU": {"label": "XLU", "latest": 70.0, "unit": "USD", "change_pct": 0.5},
    })
    monkeypatch.setattr(ts, "build_capex_summary", lambda db_path: {
        "CAPEX_MSFT": {
            "label": "Microsoft CapEx",
            "latest": 20.0,
            "qoq_pct": 1.0,
            "yoy_pct": 5.0,
        }
    })
    return calls


def test_send_report_skips_duplicate_without_force(tmp_db, monkeypatch):
    import telegram_sender as ts

    calls = _patch_report_dependencies(monkeypatch)
    mark_report_sent(db_path=tmp_db)

    ts.send_report(db_path=tmp_db, force=False)

    assert calls == []


def test_send_report_force_ignores_duplicate_and_uses_new_sections(tmp_db, monkeypatch):
    import telegram_sender as ts

    calls = _patch_report_dependencies(monkeypatch)
    mark_report_sent(db_path=tmp_db)

    ts.send_report(db_path=tmp_db, force=True)

    assert len(calls) == 1
    msg = calls[0]
    for section in ["\\[AI 병목\\]", "\\[전력 병목\\]", "\\[자본 흐름\\]", "\\[매크로 유동성\\]", "\\[이번주 이벤트\\]"]:
        assert section in msg
