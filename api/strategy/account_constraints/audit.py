from __future__ import annotations

from typing import Any

from .models import ConstraintResult


REQUIRED_AUDIT_FIELDS = {
    "account_type",
    "account_role",
    "product_id",
    "symbol",
    "intent_type",
    "requested_quantity",
    "requested_weight",
    "requested_amount",
    "adjusted_quantity",
    "adjusted_weight",
    "allowed",
    "action",
    "severity",
    "reason_codes",
    "warnings",
    "evaluated_rules",
    "as_of_date",
    "config_version",
}


def export_constraint_audit(result: ConstraintResult) -> dict[str, Any]:
    audit = dict(result.audit)
    audit.setdefault("adjusted_quantity", result.adjusted_quantity)
    audit.setdefault("adjusted_weight", result.adjusted_weight)
    audit.setdefault("allowed", result.allowed)
    audit.setdefault("action", result.action.value)
    audit.setdefault("severity", result.severity.value)
    audit.setdefault("reason_codes", list(result.reason_codes))
    audit.setdefault("warnings", list(result.warnings))
    audit.setdefault("evaluated_rules", [])
    audit.setdefault("config_version", None)
    missing = sorted(REQUIRED_AUDIT_FIELDS - set(audit))
    if missing:
        audit["missing_audit_fields"] = missing
    return audit
