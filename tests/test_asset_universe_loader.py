from pathlib import Path

import pytest
import yaml

from api.asset_universe_loader import (
    NO_ACTIVE_UNIVERSE,
    REVIEW_REQUIRED,
    AssetUniverseLoadError,
    get_asset_by_id,
    get_enabled_assets,
    get_watchlist_assets,
    load_asset_universe,
)


def _write_config(path: Path, assets: list[dict]):
    path.write_text(
        yaml.safe_dump(
            {
                "universe_id": "test_universe",
                "version": "test.1",
                "description": "Test universe",
                "base_currency": "KRW",
                "assets": assets,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def _asset(asset_id="SPY", *, enabled=True, role="core"):
    return {
        "asset_id": asset_id,
        "symbol": asset_id,
        "name": f"{asset_id} Asset",
        "asset_class": "global_equity",
        "sector": None,
        "region": "US",
        "currency": "USD",
        "instrument_type": "ETF",
        "enabled": enabled,
        "role": role,
        "risk_tier": "medium",
        "liquidity_tier": "high",
        "min_order_unit": 1,
        "data_requirements": ["price_daily"],
        "account_eligibility": {
            "taxable": {"eligible": True, "review_required": False, "restrictions": []},
            "isa": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
            "pension": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
            "irp": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
        },
        "review_required": False,
        "notes": "Test asset",
    }


def test_valid_config_loads_default_universe():
    universe = load_asset_universe()

    assert universe.universe_id == "phase1_initial_asset_universe"
    assert universe.base_currency == "KRW"
    assert get_asset_by_id(universe, "SPY") is not None


def test_missing_config_fails_conservatively(tmp_path):
    missing = tmp_path / "missing.yaml"

    with pytest.raises(AssetUniverseLoadError) as exc:
        load_asset_universe(missing)

    assert exc.value.state == NO_ACTIVE_UNIVERSE


def test_malformed_config_fails_conservatively(tmp_path):
    malformed = tmp_path / "asset_universe.yaml"
    malformed.write_text("assets: [", encoding="utf-8")

    with pytest.raises(AssetUniverseLoadError) as exc:
        load_asset_universe(malformed)

    assert exc.value.state == REVIEW_REQUIRED


def test_duplicate_asset_ids_are_rejected(tmp_path):
    path = tmp_path / "asset_universe.yaml"
    _write_config(path, [_asset("SPY"), _asset("SPY")])

    with pytest.raises(AssetUniverseLoadError, match="Duplicate asset_id"):
        load_asset_universe(path)


def test_disabled_assets_are_excluded_from_enabled_asset_list(tmp_path):
    path = tmp_path / "asset_universe.yaml"
    _write_config(path, [_asset("SPY"), _asset("DISABLED", enabled=False)])

    universe = load_asset_universe(path)

    assert {asset.asset_id for asset in get_enabled_assets(universe)} == {"SPY"}


def test_watchlist_assets_are_loaded_separately(tmp_path):
    path = tmp_path / "asset_universe.yaml"
    _write_config(path, [_asset("SPY"), _asset("WATCH", enabled=False, role="watchlist")])

    universe = load_asset_universe(path)

    assert {asset.asset_id for asset in get_enabled_assets(universe)} == {"SPY"}
    assert {asset.asset_id for asset in get_watchlist_assets(universe)} == {"WATCH"}


def test_get_asset_by_id_returns_asset_or_none():
    universe = load_asset_universe()

    assert get_asset_by_id(universe, "SPY").asset_id == "SPY"
    assert get_asset_by_id(universe, "DOES_NOT_EXIST") is None
