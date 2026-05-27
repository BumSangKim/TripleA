from __future__ import annotations


class AssetMasterValidationError(ValueError):
    pass


def validate_asset_master(asset_master: dict, schema: dict) -> None:
    for field in schema.get("required_top_level_fields", []):
        if field not in asset_master:
            raise AssetMasterValidationError(f"missing top-level field: {field}")
    assets = asset_master.get("assets")
    if not isinstance(assets, list) or not assets:
        raise AssetMasterValidationError("assets must be a non-empty list")
    for asset in assets:
        validate_asset_required_fields(asset, schema.get("required_asset_fields", []))
        _validate_asset_types(asset, schema)
        _validate_tradability(asset, schema)
        _validate_exposures(asset, schema)
        _validate_account_eligibility(asset, schema)
        _validate_data_requirements(asset, schema)
    validate_unique_assets(assets)
    validate_no_blocked_products(assets, schema.get("blocked_risk_tags", []))
    validate_stock_not_order_candidate(assets)
    validate_initial_enabled_states(assets)


def validate_asset_required_fields(asset: dict, required_fields: list[str]) -> None:
    for field in required_fields:
        if field not in asset:
            raise AssetMasterValidationError(f"{asset.get('asset_id', '<unknown>')}: missing {field}")


def validate_unique_assets(assets: list[dict]) -> None:
    asset_ids = [asset.get("asset_id") for asset in assets]
    if len(asset_ids) != len(set(asset_ids)):
        raise AssetMasterValidationError("duplicate asset_id found")
    symbol_market = [(asset.get("market"), asset.get("symbol")) for asset in assets]
    if len(symbol_market) != len(set(symbol_market)):
        raise AssetMasterValidationError("duplicate market/symbol found")


def validate_no_blocked_products(assets: list[dict], blocked_tags: list[str]) -> None:
    blocked = set(blocked_tags)
    for asset in assets:
        tags = set(asset.get("risk_tags") or [])
        overlap = sorted(tags & blocked)
        if overlap:
            raise AssetMasterValidationError(f"{asset.get('asset_id')}: blocked risk tag {overlap[0]}")


def validate_stock_not_order_candidate(assets: list[dict]) -> None:
    for asset in assets:
        if asset.get("asset_type") == "STOCK" and asset.get("tradability", {}).get("order_candidate") is not False:
            raise AssetMasterValidationError(f"{asset.get('asset_id')}: stock cannot be order candidate")


def validate_initial_enabled_states(assets: list[dict]) -> None:
    for asset in assets:
        state = asset.get("tradability", {}).get("enabled_state")
        if state == "enabled_for_order_candidate_after_approval":
            raise AssetMasterValidationError(f"{asset.get('asset_id')}: approval state not allowed initially")
        if asset.get("asset_type") == "STOCK" and state != "monitor_only":
            raise AssetMasterValidationError(f"{asset.get('asset_id')}: stock must be monitor_only")


def validate_selectors(selectors: dict) -> None:
    selector_map = selectors.get("selectors")
    if not isinstance(selector_map, dict) or not selector_map:
        raise AssetMasterValidationError("selectors must be a non-empty object")
    if _contains_key(selector_map, "asset_ids"):
        raise AssetMasterValidationError("selectors must not use asset_ids buckets")
    for name, selector in selector_map.items():
        if not isinstance(selector, dict):
            raise AssetMasterValidationError(f"{name}: selector must be an object")
        if "include" not in selector:
            raise AssetMasterValidationError(f"{name}: missing include")


def _validate_asset_types(asset: dict, schema: dict) -> None:
    if asset.get("asset_type") not in schema.get("allowed_asset_types", []):
        raise AssetMasterValidationError(f"{asset.get('asset_id')}: invalid asset_type")


def _validate_tradability(asset: dict, schema: dict) -> None:
    tradability = asset.get("tradability")
    if not isinstance(tradability, dict):
        raise AssetMasterValidationError(f"{asset.get('asset_id')}: tradability must be object")
    for field in schema.get("required_tradability_fields", []):
        if field not in tradability:
            raise AssetMasterValidationError(f"{asset.get('asset_id')}: missing tradability.{field}")
    if tradability.get("enabled_state") not in schema.get("allowed_enabled_states", []):
        raise AssetMasterValidationError(f"{asset.get('asset_id')}: invalid enabled_state")


def _validate_exposures(asset: dict, schema: dict) -> None:
    exposures = asset.get("exposures")
    if not isinstance(exposures, dict):
        raise AssetMasterValidationError(f"{asset.get('asset_id')}: exposures must be object")
    for field in schema.get("required_exposure_fields", []):
        value = exposures.get(field)
        if not isinstance(value, list) or not value:
            raise AssetMasterValidationError(f"{asset.get('asset_id')}: missing exposures.{field}")


def _validate_account_eligibility(asset: dict, schema: dict) -> None:
    eligibility = asset.get("account_eligibility")
    if not isinstance(eligibility, dict):
        raise AssetMasterValidationError(f"{asset.get('asset_id')}: account_eligibility must be object")
    allowed = set(schema.get("account_eligibility_values", []))
    for account_type in schema.get("account_types", []):
        value = eligibility.get(account_type)
        if value not in allowed:
            raise AssetMasterValidationError(f"{asset.get('asset_id')}: invalid account_eligibility.{account_type}")


def _validate_data_requirements(asset: dict, schema: dict) -> None:
    allowed = set(schema.get("allowed_data_requirements", []))
    requirements = asset.get("data_requirements")
    if not isinstance(requirements, list) or not requirements:
        raise AssetMasterValidationError(f"{asset.get('asset_id')}: data_requirements must be non-empty list")
    unknown = sorted(set(requirements) - allowed)
    if unknown:
        raise AssetMasterValidationError(f"{asset.get('asset_id')}: unknown data requirement {unknown[0]}")


def _contains_key(value, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(_contains_key(item, target) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, target) for item in value)
    return False
