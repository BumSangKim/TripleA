# tests/test_config_metadata.py
import yaml

from config import ECONOMIC_EVENTS_YAML, INDICATORS_YAML


def test_indicators_have_required_fields():
    data = yaml.safe_load(INDICATORS_YAML.read_text(encoding="utf-8"))
    required = {"id", "label", "source_type", "symbol", "unit", "frequency", "stale_days", "layer", "report_section"}
    for key, meta in data["indicators"].items():
        assert required.issubset(meta), f"{key} missing {required - set(meta)}"
        assert meta["id"] == key


def test_power_bottleneck_indicators_registered():
    data = yaml.safe_load(INDICATORS_YAML.read_text(encoding="utf-8"))
    indicators = data["indicators"]
    for key in ["ERCOT_LOAD_MW", "ERCOT_RESERVE_MARGIN", "PJM_LOAD_MW", "CAPEX_NEE", "CAPEX_DUK", "CAPEX_SO"]:
        assert key in indicators
        assert indicators[key]["report_section"] == "전력 병목"


def test_economic_events_yaml_contains_required_events():
    data = yaml.safe_load(ECONOMIC_EVENTS_YAML.read_text(encoding="utf-8"))
    names = {event["name"] for event in data["events"]}
    assert {
        "CPI",
        "Core CPI",
        "PPI",
        "NFP",
        "Unemployment Rate",
        "Average Hourly Earnings",
        "PCE",
        "FOMC",
        "GDP",
        "ISM",
        "JOLTS",
    }.issubset(names)
