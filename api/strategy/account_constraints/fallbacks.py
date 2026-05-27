from __future__ import annotations

from typing import Any

from .models import ConstraintAction, ConstraintResult, ConstraintSeverity


FALLBACK_ACTIONS = {
    ConstraintAction.NO_ACTION,
    ConstraintAction.HOLD,
    ConstraintAction.REVIEW_REQUIRED,
    ConstraintAction.RISK_REDUCE_ONLY,
}


def build_conservative_result(
    reason_code: str,
    *,
    action: ConstraintAction | str = ConstraintAction.REVIEW_REQUIRED,
    context: dict[str, Any] | None = None,
) -> ConstraintResult:
    context = context or {}
    action = ConstraintAction(action)
    if action not in FALLBACK_ACTIONS:
        action = ConstraintAction.REVIEW_REQUIRED
    blocked_fields = tuple(context.get("blocked_fields") or ())
    warnings = tuple(context.get("warnings") or ())
    audit = {
        "allowed": False,
        "action": action.value,
        "severity": ConstraintSeverity.REVIEW.value,
        "reason_codes": [reason_code],
        "warnings": list(warnings),
        "blocked_fields": list(blocked_fields),
        "evaluated_rules": list(context.get("evaluated_rules") or ("conservative_fallback",)),
        **{key: value for key, value in context.items() if key not in {"blocked_fields", "warnings", "evaluated_rules"}},
    }
    return ConstraintResult(
        allowed=False,
        action=action,
        severity=ConstraintSeverity.REVIEW,
        constraint_type="conservative_fallback",
        reason_codes=(reason_code,),
        warnings=warnings,
        blocked_fields=blocked_fields,
        review_required=action == ConstraintAction.REVIEW_REQUIRED,
        audit=audit,
    )
