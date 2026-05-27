from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AccountConstraintModelError(ValueError):
    pass


class AccountType(str, Enum):
    TAXABLE = "taxable"
    ISA = "isa"
    PENSION = "pension"
    IRP = "irp"


class AccountRole(str, Enum):
    AGGRESSIVE_GROWTH = "aggressive_growth"
    TAX_EFFICIENT_GROWTH = "tax_efficient_growth"
    LONG_TERM_GROWTH = "long_term_growth"
    DEFENSIVE_GROWTH = "defensive_growth"
    REVIEW_REQUIRED = "review_required"


class AssetClass(str, Enum):
    CASH = "cash"
    EQUITY = "equity"
    BOND = "bond"
    COMMODITY = "commodity"
    REAL_ASSET = "real_asset"
    ALTERNATIVE = "alternative"
    HEDGE = "hedge"
    UNKNOWN = "unknown"


class ConstraintSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    REVIEW = "review"
    BLOCK = "block"


class ConstraintAction(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REDUCE_ONLY = "REDUCE_ONLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NO_ACTION = "NO_ACTION"
    HOLD = "HOLD"
    RISK_REDUCE_ONLY = "RISK_REDUCE_ONLY"


class IntentType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"
    ALLOCATION = "allocation"


@dataclass(frozen=True)
class ProductFlags:
    leveraged: bool = False
    inverse: bool = False
    futures_like: bool = False
    complex_product: bool = False

    @classmethod
    def from_iterable(cls, flags: list[str] | tuple[str, ...] | set[str] | None) -> "ProductFlags":
        values = {str(flag).strip().lower() for flag in (flags or [])}
        return cls(
            leveraged="leveraged" in values,
            inverse="inverse" in values,
            futures_like="futures_like" in values,
            complex_product="complex_product" in values,
        )

    def active_flags(self) -> tuple[str, ...]:
        return tuple(
            flag
            for flag, enabled in {
                "leveraged": self.leveraged,
                "inverse": self.inverse,
                "futures_like": self.futures_like,
                "complex_product": self.complex_product,
            }.items()
            if enabled
        )


@dataclass(frozen=True)
class AccountConstraintConfig:
    account_type: AccountType
    role: AccountRole
    allow_satellite: bool | str
    allowed_asset_classes: tuple[AssetClass, ...]
    blocked_product_flags: tuple[str, ...]
    risky_asset_limit: float | None = None
    minimum_cash_buffer_ratio: float = 0.0
    unknown_behavior: ConstraintAction = ConstraintAction.REVIEW_REQUIRED
    version: str | None = None


@dataclass(frozen=True)
class PositionState:
    product_id: str
    quantity: float
    market_value: float
    is_risky_asset: bool | None = None


@dataclass(frozen=True)
class AccountState:
    account_type: AccountType
    total_value: float | None
    cash_balance: float | None
    risky_asset_value: float | None = None
    positions: tuple[PositionState, ...] = ()
    as_of_date: str | None = None


@dataclass(frozen=True)
class ProductMetadata:
    product_id: str
    symbol: str | None
    asset_class: AssetClass
    tradable: bool | None
    flags: ProductFlags = field(default_factory=ProductFlags)
    is_risky_asset: bool | None = None
    min_order_unit: float | None = None
    price: float | None = None
    market_status: str | None = "open"
    account_eligibility: dict[str, bool] = field(default_factory=dict)
    as_of_date: str | None = None


@dataclass(frozen=True)
class OrderIntent:
    intent_type: IntentType
    requested_quantity: float | None = None
    requested_weight: float | None = None
    requested_amount: float | None = None
    as_of_date: str | None = None

    @property
    def increases_risk(self) -> bool:
        return self.intent_type in {IntentType.BUY, IntentType.INCREASE, IntentType.ALLOCATION}

    @property
    def reduces_risk(self) -> bool:
        return self.intent_type in {IntentType.SELL, IntentType.DECREASE}


AllocationIntent = OrderIntent


@dataclass(frozen=True)
class ConstraintResult:
    allowed: bool
    action: ConstraintAction
    severity: ConstraintSeverity
    constraint_type: str
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    blocked_fields: tuple[str, ...] = ()
    adjusted_quantity: float | None = None
    adjusted_weight: float | None = None
    review_required: bool = False
    audit: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allow(cls, *, audit: dict[str, Any] | None = None, warnings: tuple[str, ...] = ()) -> "ConstraintResult":
        return cls(
            allowed=True,
            action=ConstraintAction.ALLOW,
            severity=ConstraintSeverity.INFO,
            constraint_type="none",
            warnings=warnings,
            review_required=False,
            audit=audit or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action": self.action.value,
            "severity": self.severity.value,
            "constraint_type": self.constraint_type,
            "reason_codes": list(self.reason_codes),
            "warnings": list(self.warnings),
            "blocked_fields": list(self.blocked_fields),
            "adjusted_quantity": self.adjusted_quantity,
            "adjusted_weight": self.adjusted_weight,
            "review_required": self.review_required,
            "audit": dict(self.audit),
        }


def account_type_from_string(value: str) -> AccountType:
    try:
        return AccountType(str(value or "").strip().lower())
    except ValueError as exc:
        raise AccountConstraintModelError(f"unknown account type: {value}") from exc
