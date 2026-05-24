# tests/test_config_metadata.py
import yaml

from api.strategy_config import (
    load_investment_universe,
    load_sector_taxonomy,
    load_strategy_profile,
    list_risk_profiles,
    list_universe_ids,
)
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


def test_default_investment_universe_contains_engine_assets():
    assert "default_global" in list_universe_ids()
    universe = load_investment_universe("default_global")
    assets = {item["asset_code"]: item for item in universe["assets"]}

    assert universe["base_currency"] == "KRW"
    assert {"SPY", "QQQ", "TLT", "CASH_KRW", "SMH"}.issubset(assets)
    assert assets["SMH"]["sector"] == "SEMICONDUCTOR"
    assert assets["CASH_KRW"]["bucket"] == "LIQUIDITY"


def test_strategy_profiles_have_valid_bucket_ranges():
    assert {"aggressive", "balanced", "defensive"}.issubset(set(list_risk_profiles()))
    for profile_id in list_risk_profiles():
        profile = load_strategy_profile(profile_id)
        total = sum(bucket["target"] for bucket in profile["buckets"].values())
        assert round(total, 6) == 1.0
        for bucket in profile["buckets"].values():
            assert bucket["min"] <= bucket["target"] <= bucket["max"]


def test_sector_taxonomy_maps_initial_bottleneck_sectors():
    sectors = load_sector_taxonomy()
    assert {"SEMICONDUCTOR", "POWER_GRID", "BATTERY"}.issubset(sectors)
    assert "SMH" in sectors["SEMICONDUCTOR"]["assets"]
    assert "HS_8507" in sectors["BATTERY"]["trade_items"]
