import pytest

from api.asset_universe_schema import (
    AssetDefinition,
    AssetUniverseSchemaError,
    get_account_eligibility,
    parse_asset_definition,
)


def _valid_asset(**overrides):
    asset = {
        "asset_id": "SPY",
        "symbol": "SPY",
        "name": "SPDR S&P 500 ETF",
        "asset_class": "global_equity",
        "sector": None,
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
        "notes": None,
    }
    asset.update(overrides)
    return asset


def test_valid_asset_schema_passes_and_serializes():
    asset = parse_asset_definition(_valid_asset())

    assert asset.asset_id == "SPY"
    assert asset.enabled is True
    assert asset.review_required is False
    assert asset.eligible_for_order_candidate is True
    assert AssetDefinition.from_dict(asset.to_dict()).to_dict() == asset.to_dict()


def test_missing_required_field_fails():
    raw = _valid_asset()
    raw.pop("currency")

    with pytest.raises(AssetUniverseSchemaError, match="currency"):
        parse_asset_definition(raw)


def test_missing_required_field_can_use_conservative_fallback():
    fallback = AssetDefinition.conservative_fallback({"asset_id": "UNKNOWN"})

    assert fallback.asset_id == "UNKNOWN"
    assert fallback.enabled is False
    assert fallback.review_required is True
    assert fallback.eligible_for_order_candidate is False


def test_unknown_role_fails_validation():
    with pytest.raises(AssetUniverseSchemaError, match="role"):
        parse_asset_definition(_valid_asset(role="aggressive_alpha"))


def test_unknown_account_eligibility_does_not_become_tradable():
    asset = parse_asset_definition(
        _valid_asset(
            account_eligibility={
                "taxable": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "isa": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "pension": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "irp": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
            }
        )
    )

    assert asset.enabled is True
    assert asset.review_required is True
    assert asset.eligible_for_order_candidate is False


def test_unknown_account_type_is_not_eligible():
    asset = parse_asset_definition(
        _valid_asset(
            account_eligibility={
                "taxable": {"eligible": True, "review_required": False, "restrictions": []},
                "isa": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "pension": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "irp": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
                "crypto_margin": {"eligible": True, "review_required": False, "restrictions": []},
            }
        )
    )
    eligibility = get_account_eligibility(asset, "crypto_margin")

    assert eligibility.eligible is False
    assert eligibility.review_required is True
    assert "unknown_account_type" in eligibility.restrictions


def test_disabled_asset_remains_excluded_from_active_universe():
    asset = parse_asset_definition(_valid_asset(enabled=False))

    assert asset.enabled is False
    assert asset.review_required is True
    assert asset.eligible_for_order_candidate is False
