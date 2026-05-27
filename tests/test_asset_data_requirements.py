from api.asset_data_requirements import (
    load_data_requirement_definitions,
    validate_data_requirement_keys,
)
from api.asset_universe_loader import load_asset_universe
from api.asset_universe_validator import validate_asset_universe_config


def _asset(asset_id="SPY", **overrides):
    asset = {
        "asset_id": asset_id,
        "symbol": asset_id,
        "name": f"{asset_id} Asset",
        "asset_class": "equity",
        "sector": "broad_market",
        "region": "US",
        "currency": "USD",
        "instrument_type": "ETF",
        "enabled": True,
        "role": "core",
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
    asset.update(overrides)
    return asset


def _config(*assets):
    return {
        "universe_id": "test_universe",
        "version": "test.1",
        "description": "Test universe",
        "base_currency": "KRW",
        "assets": list(assets),
    }


def test_enabled_asset_with_valid_data_requirements_passes():
    result = validate_asset_universe_config(_config(_asset()))

    assert result.is_valid is True


def test_enabled_asset_with_no_data_requirements_fails():
    result = validate_asset_universe_config(_config(_asset(data_requirements=[])))

    assert result.is_valid is False
    assert any(issue.field == "data_requirements" for issue in result.errors)


def test_unknown_data_requirement_fails_for_enabled_asset():
    result = validate_asset_universe_config(_config(_asset(data_requirements=["mystery_feed"])))

    assert result.is_valid is False
    assert any("unknown data requirement" in issue.message for issue in result.errors)


def test_disabled_watchlist_can_retain_incomplete_data_requirement_as_warning():
    result = validate_asset_universe_config(
        _config(
            _asset(
                "WATCH",
                enabled=False,
                role="watchlist",
                data_requirements=["REVIEW_REQUIRED"],
                review_required=True,
            )
        )
    )

    assert result.is_valid is True
    assert any(issue.field == "data_requirements" for issue in result.warnings)


def test_data_requirement_metadata_is_preserved_by_loader():
    universe = load_asset_universe()
    spy = next(asset for asset in universe.assets if asset.asset_id == "SPY")

    assert "price_daily" in spy.data_requirements
    assert "fx_daily" in spy.data_requirements


def test_data_requirement_definitions_include_canonical_keys():
    definitions = load_data_requirement_definitions()

    assert {
        "price_daily",
        "volume_daily",
        "fx_daily",
        "macro_monthly",
        "account_balance_snapshot",
    }.issubset(definitions)
    assert validate_data_requirement_keys(["price_daily"], enabled=True, role="core") == []
