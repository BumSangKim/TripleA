from __future__ import annotations

import re
from pathlib import Path

import yaml


CATALOG_PATH = Path("config/data_sources/capex_cycle_sources.yaml")
REQUIRED_METRIC_FIELDS = {
    "canonical_metric_id",
    "source_priority",
    "cadence",
    "stale_after_days",
    "expected_release_lag_days",
    "value_type",
    "unit",
    "pit_availability_rule",
}
REQUIRED_METRICS = {
    "ai_capex_yoy",
    "ai_capex_acceleration",
    "token_proxy_index",
    "macro_rate_level",
    "fx_usdkrw",
    "company_segment_growth",
    "order_backlog_growth",
    "book_to_bill",
    "consumables_growth",
    "profitability_margins",
    "valuation_inputs",
    "risk_penalty_inputs",
}


def _catalog():
    return yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))


def test_capex_cycle_data_source_yaml_parses():
    data = _catalog()

    assert data["version"] == "capex_cycle_sources_v0.1"
    assert data["source_groups"]
    assert data["metrics"]


def test_required_source_groups_and_metrics_are_present():
    data = _catalog()

    assert {"fred_alfred", "sec_edgar_companyfacts", "opendart", "ecos", "kis_readonly", "optional_licensed_vendor"}.issubset(
        data["source_groups"]
    )
    assert REQUIRED_METRICS.issubset(data["metrics"])


def test_every_metric_has_required_pit_and_staleness_metadata():
    data = _catalog()
    source_groups = set(data["source_groups"])

    for metric_name, metric in data["metrics"].items():
        assert REQUIRED_METRIC_FIELDS.issubset(metric), f"{metric_name} missing required fields"
        assert metric["source_priority"], metric_name
        assert metric["unit"], metric_name
        assert int(metric["stale_after_days"]) >= 0
        assert int(metric["expected_release_lag_days"]) >= 0
        assert "available_at" in metric["pit_availability_rule"] or "decision_time" in metric["pit_availability_rule"]
        for source in metric["source_priority"]:
            assert source["source_group"] in source_groups, f"{metric_name} references unknown source group"
            assert source["source_metric"]


def test_optional_licensed_sources_are_disabled_by_default():
    data = _catalog()
    optional_groups = [item for item in data["source_groups"].values() if item.get("optional") is True]

    assert optional_groups
    for group in optional_groups:
        assert group["enabled_by_default"] is False


def test_catalog_does_not_embed_secrets_or_raw_credentials():
    source = CATALOG_PATH.read_text(encoding="utf-8")
    secret_patterns = [
        r"(?i)\bapi[_-]?key\s*:",
        r"(?i)\bsecret\s*:",
        r"(?i)\bpassword\s*:",
        r"(?i)\bclient[_-]?secret\s*:",
        r"(?i)\bapp[_-]?secret\s*:",
    ]

    for pattern in secret_patterns:
        assert not re.search(pattern, source)
