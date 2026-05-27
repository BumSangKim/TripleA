from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ALLOWED_ROLES = {"core", "satellite", "defensive", "cash", "hedge", "watchlist"}
ALLOWED_RISK_TIERS = {"low", "medium", "high", "very_high"}
ALLOWED_LIQUIDITY_TIERS = {"low", "medium", "high"}
REQUIRED_ACCOUNT_TYPES = {"taxable", "isa", "pension", "irp"}

REQUIRED_ASSET_FIELDS = {
    "asset_id",
    "symbol",
    "name",
    "asset_class",
    "sector",
    "region",
    "currency",
    "instrument_type",
    "enabled",
    "role",
    "risk_tier",
    "liquidity_tier",
    "min_order_unit",
    "data_requirements",
    "account_eligibility",
    "notes",
}


class AssetUniverseSchemaError(ValueError):
    """Raised when asset universe metadata is incomplete or invalid."""


@dataclass(frozen=True)
class AccountEligibility:
    account_type: str
    eligible: bool
    review_required: bool
    restrictions: list[str]

    def is_actionable(self) -> bool:
        return self.eligible and not self.review_required and not self.restrictions


@dataclass(frozen=True)
class AssetDefinition:
    asset_id: str
    symbol: str
    name: str
    asset_class: str
    sector: str | None
    region: str
    currency: str
    instrument_type: str
    enabled: bool
    role: str
    risk_tier: str
    liquidity_tier: str
    min_order_unit: float | None
    data_requirements: list[str]
    account_eligibility: dict[str, AccountEligibility]
    notes: str | None
    review_required: bool = False
    eligible_for_order_candidate: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AssetDefinition":
        missing = sorted(REQUIRED_ASSET_FIELDS - set(raw))
        if missing:
            raise AssetUniverseSchemaError(f"Missing required asset fields: {', '.join(missing)}")

        asset = cls(
            asset_id=_required_string(raw, "asset_id"),
            symbol=_required_string(raw, "symbol"),
            name=_required_string(raw, "name"),
            asset_class=_required_string(raw, "asset_class"),
            sector=_optional_string(raw, "sector"),
            region=_required_string(raw, "region"),
            currency=_required_string(raw, "currency"),
            instrument_type=_required_string(raw, "instrument_type"),
            enabled=_required_bool(raw, "enabled"),
            role=_enum(raw, "role", ALLOWED_ROLES),
            risk_tier=_enum(raw, "risk_tier", ALLOWED_RISK_TIERS),
            liquidity_tier=_enum(raw, "liquidity_tier", ALLOWED_LIQUIDITY_TIERS),
            min_order_unit=_optional_number(raw, "min_order_unit"),
            data_requirements=_string_list(raw, "data_requirements"),
            account_eligibility=_eligibility(raw, "account_eligibility"),
            notes=_optional_string(raw, "notes"),
            review_required=_optional_bool(raw, "review_required") or False,
        )
        return asset._with_conservative_flags()

    @classmethod
    def conservative_fallback(cls, raw: dict[str, Any] | None = None) -> "AssetDefinition":
        raw = raw or {}
        asset_id = str(raw.get("asset_id") or raw.get("asset_code") or "REVIEW_REQUIRED").strip()
        return cls(
            asset_id=asset_id or "REVIEW_REQUIRED",
            symbol=str(raw.get("symbol") or "").strip(),
            name=str(raw.get("name") or "Review Required Asset").strip(),
            asset_class=str(raw.get("asset_class") or "REVIEW_REQUIRED").strip(),
            sector=_safe_optional_string(raw.get("sector")),
            region=str(raw.get("region") or "REVIEW_REQUIRED").strip(),
            currency=str(raw.get("currency") or "REVIEW_REQUIRED").strip(),
            instrument_type=str(raw.get("instrument_type") or "REVIEW_REQUIRED").strip(),
            enabled=False,
            role="watchlist",
            risk_tier="very_high",
            liquidity_tier="low",
            min_order_unit=None,
            data_requirements=[],
            account_eligibility={},
            notes=_safe_optional_string(raw.get("notes")) or "REVIEW_REQUIRED",
            review_required=True,
            eligible_for_order_candidate=False,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def _with_conservative_flags(self) -> "AssetDefinition":
        review_required = self.review_required or _requires_review(self)
        return AssetDefinition(
            asset_id=self.asset_id,
            symbol=self.symbol,
            name=self.name,
            asset_class=self.asset_class,
            sector=self.sector,
            region=self.region,
            currency=self.currency,
            instrument_type=self.instrument_type,
            enabled=self.enabled,
            role=self.role,
            risk_tier=self.risk_tier,
            liquidity_tier=self.liquidity_tier,
            min_order_unit=self.min_order_unit,
            data_requirements=list(self.data_requirements),
            account_eligibility=dict(self.account_eligibility),
            notes=self.notes,
            review_required=review_required,
            eligible_for_order_candidate=self.enabled and not review_required,
        )


def parse_asset_definition(raw: dict[str, Any]) -> AssetDefinition:
    return AssetDefinition.from_dict(raw)


def parse_asset_definitions(raw_assets: list[dict[str, Any]]) -> list[AssetDefinition]:
    return [parse_asset_definition(raw) for raw in raw_assets]


def get_account_eligibility(asset: AssetDefinition, account_type: str) -> AccountEligibility:
    normalized = (account_type or "").strip().lower()
    eligibility = asset.account_eligibility.get(normalized)
    if eligibility:
        return eligibility
    return AccountEligibility(
        account_type=normalized or "unknown",
        eligible=False,
        review_required=True,
        restrictions=["missing_account_eligibility"],
    )


def _required_string(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AssetUniverseSchemaError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_string(raw: dict[str, Any], field: str) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AssetUniverseSchemaError(f"{field} must be a string or null")
    return value.strip() or None


def _required_bool(raw: dict[str, Any], field: str) -> bool:
    value = raw.get(field)
    if not isinstance(value, bool):
        raise AssetUniverseSchemaError(f"{field} must be a boolean")
    return value


def _optional_bool(raw: dict[str, Any], field: str) -> bool | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise AssetUniverseSchemaError(f"{field} must be a boolean")
    return value


def _enum(raw: dict[str, Any], field: str, allowed: set[str]) -> str:
    value = _required_string(raw, field)
    if value not in allowed:
        allowed_values = ", ".join(sorted(allowed))
        raise AssetUniverseSchemaError(f"{field} must be one of: {allowed_values}")
    return value


def _optional_number(raw: dict[str, Any], field: str) -> float | None:
    value = raw.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AssetUniverseSchemaError(f"{field} must be a number or null")
    if value < 0:
        raise AssetUniverseSchemaError(f"{field} must not be negative")
    return float(value)


def _string_list(raw: dict[str, Any], field: str) -> list[str]:
    value = raw.get(field)
    if not isinstance(value, list):
        raise AssetUniverseSchemaError(f"{field} must be a list of strings")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AssetUniverseSchemaError(f"{field} must contain only non-empty strings")
        result.append(item.strip())
    return result


def _eligibility(raw: dict[str, Any], field: str) -> dict[str, str]:
    value = raw.get(field)
    if not isinstance(value, dict):
        raise AssetUniverseSchemaError(f"{field} must be an object")
    result: dict[str, AccountEligibility] = {}
    for account_type, metadata in value.items():
        if not isinstance(account_type, str) or not account_type.strip():
            raise AssetUniverseSchemaError(f"{field} keys must be non-empty strings")
        normalized_account = account_type.strip().lower()
        if not isinstance(metadata, dict):
            raise AssetUniverseSchemaError(f"{field}.{account_type} must be an object")
        unknown_account = normalized_account not in REQUIRED_ACCOUNT_TYPES
        eligible = _required_bool(metadata, "eligible")
        review_required = _required_bool(metadata, "review_required") or unknown_account
        restrictions = _string_list(metadata, "restrictions")
        if unknown_account and "unknown_account_type" not in restrictions:
            restrictions = [*restrictions, "unknown_account_type"]
        result[normalized_account] = AccountEligibility(
            account_type=normalized_account,
            eligible=eligible and not unknown_account,
            review_required=review_required,
            restrictions=restrictions,
        )
    return result


def _requires_review(asset: AssetDefinition) -> bool:
    if not asset.enabled:
        return True
    if not asset.account_eligibility:
        return True
    if not asset.data_requirements:
        return True
    return not any(item.is_actionable() for item in asset.account_eligibility.values())


def _safe_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
