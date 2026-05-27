from pathlib import Path

import yaml

from api.asset_universe_schema import parse_asset_definitions


ASSET_UNIVERSE_CONFIG = Path("config/asset_universe.yaml")


def _load_config_assets():
    data = yaml.safe_load(ASSET_UNIVERSE_CONFIG.read_text(encoding="utf-8"))
    return data, parse_asset_definitions(data["assets"])


def test_asset_universe_config_file_exists():
    assert ASSET_UNIVERSE_CONFIG.exists()


def test_asset_universe_config_can_be_parsed():
    data, assets = _load_config_assets()

    assert data["universe_id"] == "phase6_backtest_asset_universe_20210101"
    assert data["base_currency"] == "KRW"
    assert data["backtest_start_date"] == "2021-01-01"
    assert assets


def test_every_asset_has_unique_asset_id():
    _, assets = _load_config_assets()
    asset_ids = [asset.asset_id for asset in assets]

    assert len(asset_ids) == len(set(asset_ids))


def test_config_contains_required_representative_assets():
    _, assets = _load_config_assets()
    roles = {asset.role for asset in assets}

    assert {"cash", "core", "defensive", "satellite", "hedge"}.issubset(roles)
    assert any(asset.region == "KR" and asset.role == "core" for asset in assets)
    assert any(asset.region == "US" and asset.role == "core" for asset in assets)


def test_every_asset_has_required_metadata_behavior():
    raw_data = yaml.safe_load(ASSET_UNIVERSE_CONFIG.read_text(encoding="utf-8"))
    for raw in raw_data["assets"]:
        assert isinstance(raw.get("enabled"), bool)
        assert "notes" in raw and raw["notes"]
        assert raw.get("account_eligibility")
        assert raw.get("data_requirements")
        assert isinstance(raw.get("review_required"), bool)


def test_disabled_and_watchlist_assets_do_not_appear_in_active_universe():
    _, assets = _load_config_assets()
    active_assets = [
        asset
        for asset in assets
        if asset.enabled and asset.role != "watchlist" and asset.eligible_for_order_candidate
    ]

    assert "ROBOT_WATCHLIST" not in {asset.asset_id for asset in active_assets}
    assert not active_assets
    assert all(asset.role != "watchlist" for asset in active_assets)


def test_backtest_candidate_universe_remains_conservative():
    _, assets = _load_config_assets()

    assert {asset.asset_id for asset in assets} == {
        "CASH_KRW",
        "KOSPI_INDEX",
        "SPY",
        "QQQ",
        "IWM",
        "EFA",
        "EEM",
        "SHY",
        "IEF",
        "TLT",
        "LQD",
        "GLD",
        "DBC",
        "VNQ",
        "SMH",
        "BOTZ",
    }
    assert all(asset.review_required is True for asset in assets)
    assert all(asset.eligible_for_order_candidate is False for asset in assets)
    assert all("not a buy" in (asset.notes or "") for asset in assets)


def test_foreign_etfs_are_taxable_only_until_review():
    _, assets = _load_config_assets()

    for asset in assets:
        if asset.currency != "USD" or asset.instrument_type != "ETF":
            continue
        assert asset.account_eligibility["taxable"].eligible is True
        for account_type in ("isa", "pension", "irp"):
            assert asset.account_eligibility[account_type].eligible is False
            assert asset.account_eligibility[account_type].review_required is True


def test_config_uses_required_account_types():
    _, assets = _load_config_assets()

    for asset in assets:
        assert {"taxable", "isa", "pension", "irp"}.issubset(asset.account_eligibility)
