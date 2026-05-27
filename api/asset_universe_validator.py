from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .asset_data_requirements import validate_data_requirement_keys
from .asset_universe_loader import NO_ACTION, AssetUniverse
from .asset_universe_schema import (
    AssetDefinition,
    AssetUniverseSchemaError,
    REQUIRED_ACCOUNT_TYPES,
    parse_asset_definition,
)


@dataclass(frozen=True)
class ValidationIssue:
    asset_id: str | None
    field: str
    message: str


@dataclass(frozen=True)
class AssetUniverseValidationResult:
    is_valid: bool
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    review_required_assets: list[str]
    active_asset_count: int
    conservative_state: str | None = None


def validate_asset_universe(universe: AssetUniverse) -> AssetUniverseValidationResult:
    return _result_for_assets(universe.assets)


def validate_asset_universe_config(raw: dict[str, Any]) -> AssetUniverseValidationResult:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    parsed_assets: list[AssetDefinition] = []

    raw_assets = raw.get("assets") if isinstance(raw, dict) else None
    if not isinstance(raw_assets, list):
        return AssetUniverseValidationResult(
            is_valid=False,
            errors=[ValidationIssue(None, "assets", "assets must be a list")],
            warnings=[],
            review_required_assets=[],
            active_asset_count=0,
            conservative_state=NO_ACTION,
        )

    errors.extend(_duplicate_errors_from_raw(raw_assets))
    for index, raw_asset in enumerate(raw_assets):
        if not isinstance(raw_asset, dict):
            errors.append(ValidationIssue(None, f"assets[{index}]", "asset entry must be an object"))
            continue
        asset_id = str(raw_asset.get("asset_id") or f"assets[{index}]")
        if raw_asset.get("enabled") is False and raw_asset.get("eligible_for_order_candidate") is True:
            errors.append(
                ValidationIssue(
                    asset_id,
                    "eligible_for_order_candidate",
                    "disabled asset must not be marked tradable",
                )
            )
        try:
            parsed_assets.append(parse_asset_definition(raw_asset))
        except AssetUniverseSchemaError as exc:
            errors.append(ValidationIssue(asset_id, "schema", str(exc)))

    parsed_result = _result_for_assets(parsed_assets)
    errors.extend(parsed_result.errors)
    warnings.extend(parsed_result.warnings)
    review_required_assets = sorted(
        set(parsed_result.review_required_assets)
        | {
            str(raw_asset.get("asset_id"))
            for raw_asset in raw_assets
            if isinstance(raw_asset, dict) and raw_asset.get("review_required") is True
        }
    )
    is_valid = not errors
    return AssetUniverseValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        review_required_assets=review_required_assets,
        active_asset_count=parsed_result.active_asset_count,
        conservative_state=None if is_valid else NO_ACTION,
    )


def _result_for_assets(assets: Iterable[AssetDefinition]) -> AssetUniverseValidationResult:
    asset_list = list(assets)
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    errors.extend(_duplicate_errors_from_assets(asset_list))
    for asset in asset_list:
        errors.extend(_blocking_asset_errors(asset))
        warnings.extend(_data_requirement_warnings(asset))
        warnings.extend(_asset_warnings(asset))

    review_required_assets = sorted(
        asset.asset_id
        for asset in asset_list
        if asset.review_required or any(issue.asset_id == asset.asset_id for issue in warnings)
    )
    active_asset_count = sum(1 for asset in asset_list if asset.enabled and asset.role != "watchlist")
    is_valid = not errors
    return AssetUniverseValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        review_required_assets=review_required_assets,
        active_asset_count=active_asset_count,
        conservative_state=None if is_valid else NO_ACTION,
    )


def _blocking_asset_errors(asset: AssetDefinition) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    if asset.enabled and not asset.account_eligibility:
        errors.append(
            ValidationIssue(asset.asset_id, "account_eligibility", "enabled asset has no account eligibility metadata")
        )
    if asset.enabled:
        missing_account_types = REQUIRED_ACCOUNT_TYPES - set(asset.account_eligibility)
        if missing_account_types:
            errors.append(
                ValidationIssue(
                    asset.asset_id,
                    "account_eligibility",
                    "enabled asset is missing account eligibility for: "
                    + ", ".join(sorted(missing_account_types)),
                )
            )
    if asset.enabled and not asset.data_requirements:
        errors.append(
            ValidationIssue(asset.asset_id, "data_requirements", "enabled asset has no data requirements")
        )
    for issue in validate_data_requirement_keys(
        asset.data_requirements,
        enabled=asset.enabled,
        role=asset.role,
    ):
        if asset.enabled:
            errors.append(ValidationIssue(asset.asset_id, "data_requirements", issue))
    if asset.enabled and asset.instrument_type.strip().lower() in {"unknown", "review_required"}:
        errors.append(
            ValidationIssue(asset.asset_id, "instrument_type", "enabled asset has unknown instrument type")
        )
    if not asset.enabled and asset.eligible_for_order_candidate:
        errors.append(
            ValidationIssue(asset.asset_id, "eligible_for_order_candidate", "disabled asset is marked tradable")
        )
    return errors


def _data_requirement_warnings(asset: AssetDefinition) -> list[ValidationIssue]:
    if asset.enabled:
        return []
    return [
        ValidationIssue(asset.asset_id, "data_requirements", issue)
        for issue in validate_data_requirement_keys(
            asset.data_requirements,
            enabled=asset.enabled,
            role=asset.role,
        )
    ]


def _asset_warnings(asset: AssetDefinition) -> list[ValidationIssue]:
    warnings: list[ValidationIssue] = []
    high_risk = asset.risk_tier in {"high", "very_high"}
    if asset.role == "satellite" and not asset.notes:
        warnings.append(ValidationIssue(asset.asset_id, "notes", "satellite asset is missing notes"))
    if high_risk and not asset.notes:
        warnings.append(ValidationIssue(asset.asset_id, "notes", "high-risk asset is missing notes"))
    if asset.risk_tier == "very_high" and not asset.review_required:
        warnings.append(
            ValidationIssue(asset.asset_id, "review_required", "very high risk asset should require explicit review")
        )
    if asset.role == "satellite" and not asset.sector:
        warnings.append(ValidationIssue(asset.asset_id, "sector", "sector-linked satellite asset is missing sector"))
    if asset.asset_class in {"sector_equity", "thematic_equity"} and not asset.sector:
        warnings.append(ValidationIssue(asset.asset_id, "sector", "sector-linked asset class is missing sector"))
    if asset.region == "KR" and asset.currency != "KRW":
        warnings.append(ValidationIssue(asset.asset_id, "currency", "KR region asset uses non-KRW currency"))
    if asset.role != "cash" and asset.enabled and asset.min_order_unit is None:
        warnings.append(ValidationIssue(asset.asset_id, "min_order_unit", "enabled non-cash asset has no min order unit"))
    for account_type, eligibility in asset.account_eligibility.items():
        if account_type not in REQUIRED_ACCOUNT_TYPES:
            warnings.append(
                ValidationIssue(asset.asset_id, "account_eligibility", f"unknown account type: {account_type}")
            )
        if eligibility.review_required:
            warnings.append(
                ValidationIssue(asset.asset_id, "account_eligibility", f"{account_type} requires review")
            )
    return warnings


def _duplicate_errors_from_assets(assets: list[AssetDefinition]) -> list[ValidationIssue]:
    seen: set[str] = set()
    errors: list[ValidationIssue] = []
    for asset in assets:
        if asset.asset_id in seen:
            errors.append(ValidationIssue(asset.asset_id, "asset_id", "duplicate asset_id"))
        seen.add(asset.asset_id)
    return errors


def _duplicate_errors_from_raw(raw_assets: list[Any]) -> list[ValidationIssue]:
    seen: set[str] = set()
    errors: list[ValidationIssue] = []
    for raw_asset in raw_assets:
        if not isinstance(raw_asset, dict):
            continue
        asset_id = raw_asset.get("asset_id")
        if not isinstance(asset_id, str) or not asset_id:
            continue
        if asset_id in seen:
            errors.append(ValidationIssue(asset_id, "asset_id", "duplicate asset_id"))
        seen.add(asset_id)
    return errors
