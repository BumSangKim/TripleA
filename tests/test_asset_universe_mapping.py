from api.asset_universe_loader import load_asset_universe
from api.asset_universe_mapping import (
    AssetUniverseMappingError,
    load_asset_universe_mapping,
    normalize_asset_class,
    normalize_sector,
    validate_asset_categories,
)
from api.asset_universe_schema import AssetDefinition


def _asset(**overrides):
    raw = {
        "asset_id": "SMH",
        "symbol": "SMH",
        "name": "Semiconductor ETF",
        "asset_class": "equity",
        "sector": "semiconductor",
        "region": "US",
        "currency": "USD",
        "instrument_type": "ETF",
        "enabled": True,
        "role": "satellite",
        "risk_tier": "very_high",
        "liquidity_tier": "high",
        "min_order_unit": 1,
        "data_requirements": ["price_daily"],
        "account_eligibility": {
            "taxable": {"eligible": True, "review_required": False, "restrictions": []},
            "isa": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
            "pension": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
            "irp": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
        },
        "review_required": True,
        "notes": "Test asset",
    }
    raw.update(overrides)
    return AssetDefinition.from_dict(raw)


def test_all_configured_assets_use_canonical_asset_classes():
    mapping = load_asset_universe_mapping()
    universe = load_asset_universe()

    for asset in universe.assets:
        assert normalize_asset_class(asset.asset_class, mapping) == asset.asset_class


def test_all_configured_assets_use_canonical_sectors_or_none():
    mapping = load_asset_universe_mapping()
    universe = load_asset_universe()

    for asset in universe.assets:
        assert normalize_sector(asset.sector, mapping) == asset.sector


def test_unknown_asset_class_is_rejected_for_enabled_asset():
    issues = validate_asset_categories(_asset(asset_class="mystery"))

    assert any("unknown asset_class" in issue for issue in issues)


def test_unknown_sector_is_rejected_for_enabled_asset():
    issues = validate_asset_categories(_asset(sector="mystery_sector"))

    assert any("unknown sector" in issue for issue in issues)


def test_aliases_normalize_only_through_explicit_mapping():
    mapping = load_asset_universe_mapping()

    assert normalize_asset_class("domestic_equity", mapping) == "equity"
    assert normalize_sector("SEMICONDUCTOR", mapping) == "semiconductor"


def test_unmapped_alias_raises():
    mapping = load_asset_universe_mapping()

    try:
        normalize_asset_class("growth_bucket", mapping)
        raised = False
    except AssetUniverseMappingError:
        raised = True

    assert raised is True
