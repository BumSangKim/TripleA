from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token")
NORMAL_FIXTURES = [
    FIXTURE_DIR / "s1_expanding_accelerating.json",
    FIXTURE_DIR / "s3_expanding_decelerating_platform.json",
    FIXTURE_DIR / "s7_contracting_accelerating_overinvestment.json",
]
INVALID_AMBIGUOUS = FIXTURE_DIR / "invalid_ambiguous_period_roles.json"
LEAKAGE_PROBE = FIXTURE_DIR / "future_data_leakage_probe.json"


def test_normal_fixtures_have_required_explicit_schema():
    for path in NORMAL_FIXTURES:
        data = _load(path)
        _assert_required_snapshot_fields(data)
        assert data["metadata"]["synthetic"] is True
        assert all(item["period_role"] == "current" for item in data["token_sources_current"])
        assert all(item["period_role"] == "previous" for item in data["token_sources_previous"])
        assert {item["period_role"] for item in data["capex_series"]} == {"t", "t_minus_1", "t_minus_2"}
        assert data["sector_metrics"]
        assert data["macro_overlay_metrics"]


def test_invalid_ambiguous_period_fixture_fails_validation():
    data = _load(INVALID_AMBIGUOUS)

    with pytest.raises(AssertionError):
        _assert_required_snapshot_fields(data)


def test_future_leakage_probe_has_future_available_at_rows():
    data = _load(LEAKAGE_PROBE)
    _assert_required_snapshot_fields(data)
    decision_dt = datetime.fromisoformat(data["decision_date"] + "T23:59:59")
    all_rows = [*data["token_sources_current"], *data["token_sources_previous"], *data["capex_series"]]

    assert any(datetime.fromisoformat(row["available_at"]) > decision_dt for row in all_rows)


def test_fixture_source_names_are_not_needed_for_period_roles():
    for path in NORMAL_FIXTURES:
        data = _load(path)
        for row in [*data["token_sources_current"], *data["token_sources_previous"], *data["capex_series"]]:
            assert "period_role" in row
            assert row["source"] == "synthetic_fixture"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_required_snapshot_fields(data: dict) -> None:
    for field in ("decision_date", "snapshot_id", "token_sources_current", "token_sources_previous", "capex_series", "sector_metrics", "macro_overlay_metrics"):
        assert field in data
    for row in [*data["token_sources_current"], *data["token_sources_previous"], *data["capex_series"]]:
        for field in ("metric_key", "period_role", "value", "as_of_date", "available_at", "source", "quality_score", "missing_ratio", "is_stale"):
            assert field in row
    assert all(row["period_role"] == "current" for row in data["token_sources_current"])
    assert all(row["period_role"] == "previous" for row in data["token_sources_previous"])
    assert {row["period_role"] for row in data["capex_series"]} == {"t", "t_minus_1", "t_minus_2"}
