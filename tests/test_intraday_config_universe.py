from api.intraday.config import (
    IntradayMonitoringConfig,
    load_intraday_config,
    monitoring_thresholds_are_strategy_parameters,
)
from api.intraday.universe import resolve_intraday_universe
from api.universe.loader import load_assets


def test_intraday_config_loads_successfully():
    config = load_intraday_config()

    assert config.enabled is True
    assert config.collection_interval_seconds == 60
    assert config.market_session_policy == "full_regular_session"
    assert config.provider == "mock"
    assert config.surge_thresholds["warning"] == 4.0


def test_intraday_config_applies_defaults_when_optional_values_absent(tmp_path):
    path = tmp_path / "intraday_monitoring.yaml"
    path.write_text("intraday_monitoring:\n  enabled: true\n", encoding="utf-8")

    config = load_intraday_config(path)

    assert config.collection_interval_seconds == 60
    assert config.lookback_windows_minutes == (1, 3, 5, 10, 15, 30)
    assert config.duplicate_suppression_minutes == 10
    assert config.stale_data_tolerance_seconds == 120
    assert config.max_symbols_per_batch == 100


def test_disabled_intraday_monitoring_returns_empty_universe():
    config = IntradayMonitoringConfig(enabled=False)

    assert resolve_intraday_universe(config, assets=[], selectors={}) == []


def test_intraday_universe_returns_enabled_supported_investable_symbols():
    symbols = resolve_intraday_universe(load_intraday_config())

    assert symbols
    assert all(item.market == "KRX" for item in symbols)
    assert {"005930", "000660"}.issubset({item.symbol for item in symbols})
    assert "NVDA" not in {item.symbol for item in symbols}


def test_intraday_universe_excludes_missing_or_unsupported_symbols():
    assets = [
        {
            "asset_id": "KRX_VALID",
            "symbol": "123456",
            "name": "Valid",
            "market": "KRX",
            "asset_type": "ETF",
            "tradability": {"enabled_state": "monitor_only", "order_candidate": False},
        },
        {
            "asset_id": "KRX_MISSING",
            "symbol": "",
            "name": "Missing Symbol",
            "market": "KRX",
            "asset_type": "ETF",
            "tradability": {"enabled_state": "monitor_only", "order_candidate": False},
        },
        {
            "asset_id": "US_UNSUPPORTED",
            "symbol": "NVDA",
            "name": "Unsupported",
            "market": "NASDAQ",
            "asset_type": "STOCK",
            "tradability": {"enabled_state": "monitor_only", "order_candidate": False},
        },
    ]

    symbols = resolve_intraday_universe(IntradayMonitoringConfig(provider="mock"), assets=assets, selectors={})

    assert [item.symbol for item in symbols] == ["123456"]


def test_optional_selector_can_narrow_universe_without_hardcoding_symbols():
    selectors = {
        "krx_etfs": {
            "include": {"asset_type": {"any": ["ETF"]}, "market": {"any": ["KRX"]}},
            "exclude": {},
        }
    }

    symbols = resolve_intraday_universe(
        IntradayMonitoringConfig(universe_selector="krx_etfs"),
        assets=load_assets("config/universe"),
        selectors=selectors,
    )

    assert symbols
    assert all(item.asset_type == "ETF" for item in symbols)


def test_intraday_thresholds_are_not_strategy_parameters():
    assert monitoring_thresholds_are_strategy_parameters() is False
