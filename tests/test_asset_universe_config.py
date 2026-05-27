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

    assert data["universe_id"] == "phase1_initial_asset_universe"
    assert data["base_currency"] == "KRW"
    assert assets


def test_every_asset_has_unique_asset_id():
    _, assets = _load_config_assets()
    asset_ids = [asset.asset_id for asset in assets]

    assert len(asset_ids) == len(set(asset_ids))


def test_config_contains_required_representative_assets():
    _, assets = _load_config_assets()
    roles = {asset.role for asset in assets}

    assert {"cash", "core", "defensive", "satellite", "watchlist"}.issubset(roles)
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
    assert all(asset.role != "watchlist" for asset in active_assets)


def test_unknown_account_eligibility_remains_conservative():
    _, assets = _load_config_assets()
    watchlist = next(asset for asset in assets if asset.asset_id == "ROBOT_WATCHLIST")

    assert all(item.eligible is False for item in watchlist.account_eligibility.values())
    assert all(item.review_required is True for item in watchlist.account_eligibility.values())
    assert watchlist.enabled is False
    assert watchlist.review_required is True
    assert watchlist.eligible_for_order_candidate is False


def test_config_uses_required_account_types():
    _, assets = _load_config_assets()

    for asset in assets:
        assert {"taxable", "isa", "pension", "irp"}.issubset(asset.account_eligibility)
