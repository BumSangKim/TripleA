from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from api.asset_universe_loader import PROJECT_ROOT


DEFAULT_ACCOUNT_CONSTRAINTS_PATH = PROJECT_ROOT / "config" / "account_constraints.yaml"
SUPPORTED_ACCOUNT_TYPES = {"taxable", "isa", "pension", "irp"}
SUPPORTED_UNKNOWN_BEHAVIORS = {"NO_ACTION", "HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}


class AccountConstraintConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AccountRuleConfig:
    account_type: str
    role: str
    allow_satellite: bool | str
    allowed_asset_classes: tuple[str, ...]
    blocked_product_flags: tuple[str, ...]
    max_account_weight_by_asset_class: dict[str, float]
    risky_asset_limit: float | None
    minimum_cash_buffer_ratio: float
    unknown_behavior: str


@dataclass(frozen=True)
class AccountConstraintSet:
    version: str
    unknown_account_behavior: str
    accounts: dict[str, AccountRuleConfig]

    def get(self, account_type: str) -> AccountRuleConfig | None:
        return self.accounts.get(str(account_type or "").strip().lower())


def load_account_constraint_config(path: str | Path | None = None) -> AccountConstraintSet:
    config_path = Path(path) if path is not None else DEFAULT_ACCOUNT_CONSTRAINTS_PATH
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise AccountConstraintConfigError("account constraint config must be an object")
    version = _required_string(raw, "version")
    unknown_account_behavior = _unknown_behavior(raw.get("unknown_account_behavior"), "unknown_account_behavior")
    accounts_raw = raw.get("accounts")
    if not isinstance(accounts_raw, dict) or not accounts_raw:
        raise AccountConstraintConfigError("accounts must be a non-empty object")
    accounts = {
        account_key.strip().lower(): _account_rule(account_key, value)
        for account_key, value in accounts_raw.items()
    }
    missing = SUPPORTED_ACCOUNT_TYPES - set(accounts)
    if missing:
        raise AccountConstraintConfigError(f"missing account configs: {', '.join(sorted(missing))}")
    return AccountConstraintSet(
        version=version,
        unknown_account_behavior=unknown_account_behavior,
        accounts=accounts,
    )


def _account_rule(account_key: str, raw: Any) -> AccountRuleConfig:
    if not isinstance(account_key, str) or not account_key.strip():
        raise AccountConstraintConfigError("account key must be a non-empty string")
    normalized_key = account_key.strip().lower()
    if normalized_key not in SUPPORTED_ACCOUNT_TYPES:
        raise AccountConstraintConfigError(f"unknown account type: {account_key}")
    if not isinstance(raw, dict):
        raise AccountConstraintConfigError(f"accounts.{account_key} must be an object")
    account_type = _required_string(raw, "type").lower()
    if account_type != normalized_key:
        raise AccountConstraintConfigError(f"accounts.{account_key}.type must match the account key")
    risky_asset_limit = _optional_ratio(raw.get("risky_asset_limit"), f"accounts.{account_key}.risky_asset_limit")
    if normalized_key == "irp" and risky_asset_limit is None:
        raise AccountConstraintConfigError("accounts.irp.risky_asset_limit is required")
    return AccountRuleConfig(
        account_type=account_type,
        role=_required_string(raw, "role"),
        allow_satellite=_allow_satellite(raw.get("allow_satellite"), f"accounts.{account_key}.allow_satellite"),
        allowed_asset_classes=_string_tuple(raw.get("allowed_asset_classes"), f"accounts.{account_key}.allowed_asset_classes"),
        blocked_product_flags=_string_tuple(raw.get("blocked_product_flags"), f"accounts.{account_key}.blocked_product_flags"),
        max_account_weight_by_asset_class=_ratio_map(
            raw.get("max_account_weight_by_asset_class", {}),
            f"accounts.{account_key}.max_account_weight_by_asset_class",
        ),
        risky_asset_limit=risky_asset_limit,
        minimum_cash_buffer_ratio=_ratio(raw.get("minimum_cash_buffer_ratio"), f"accounts.{account_key}.minimum_cash_buffer_ratio"),
        unknown_behavior=_unknown_behavior(raw.get("unknown_behavior"), f"accounts.{account_key}.unknown_behavior"),
    )


def _required_string(raw: dict[str, Any], field: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AccountConstraintConfigError(f"{field} must be a non-empty string")
    return value.strip()


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise AccountConstraintConfigError(f"{field} must be a non-empty list")
    result = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise AccountConstraintConfigError(f"{field} contains an invalid item")
        result.append(item.strip())
    return tuple(result)


def _ratio(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AccountConstraintConfigError(f"{field} must be a ratio number")
    number = float(value)
    if number < 0 or number > 1:
        raise AccountConstraintConfigError(f"{field} must be between 0 and 1")
    return number


def _optional_ratio(value: Any, field: str) -> float | None:
    if value is None:
        return None
    return _ratio(value, field)


def _ratio_map(value: Any, field: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise AccountConstraintConfigError(f"{field} must be an object")
    result = {}
    for key, raw_ratio in value.items():
        if not isinstance(key, str) or not key.strip():
            raise AccountConstraintConfigError(f"{field} contains an invalid key")
        result[key.strip()] = _ratio(raw_ratio, f"{field}.{key}")
    return result


def _allow_satellite(value: Any, field: str) -> bool | str:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip() == "limited":
        return "limited"
    raise AccountConstraintConfigError(f"{field} must be true, false, or limited")


def _unknown_behavior(value: Any, field: str) -> str:
    if not isinstance(value, str) or value.strip() not in SUPPORTED_UNKNOWN_BEHAVIORS:
        allowed = ", ".join(sorted(SUPPORTED_UNKNOWN_BEHAVIORS))
        raise AccountConstraintConfigError(f"{field} must be one of: {allowed}")
    return value.strip()
