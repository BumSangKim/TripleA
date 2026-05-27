"""Account constraint contracts and validators."""

from .config import (
    AccountConstraintConfigError,
    AccountRuleConfig,
    AccountConstraintSet,
    load_account_constraint_config,
)
from .audit import REQUIRED_AUDIT_FIELDS, export_constraint_audit
from .models import (
    AccountConstraintConfig,
    AccountState,
    AccountType,
    AllocationIntent,
    AssetClass,
    ConstraintAction,
    ConstraintResult,
    ConstraintSeverity,
    IntentType,
    OrderIntent,
    PositionState,
    ProductFlags,
    ProductMetadata,
)
from .engine import evaluate_account_constraints
from .eligibility import product_metadata_from_asset_definition, validate_trade_eligibility
from .fallbacks import build_conservative_result

__all__ = [
    "AccountConstraintConfig",
    "AccountConstraintConfigError",
    "AccountConstraintSet",
    "AccountRuleConfig",
    "AccountState",
    "AccountType",
    "AllocationIntent",
    "AssetClass",
    "ConstraintAction",
    "ConstraintResult",
    "ConstraintSeverity",
    "IntentType",
    "OrderIntent",
    "PositionState",
    "ProductFlags",
    "ProductMetadata",
    "REQUIRED_AUDIT_FIELDS",
    "build_conservative_result",
    "evaluate_account_constraints",
    "export_constraint_audit",
    "load_account_constraint_config",
    "product_metadata_from_asset_definition",
    "validate_trade_eligibility",
]
