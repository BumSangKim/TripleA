from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from api.domain.decision_feedback import (
    FeedbackContractError,
    FeedbackSeverity,
    FeedbackSignal,
    FeedbackSourceLayer,
    FeedbackTargetLayer,
    FeedbackTiming,
    risk_reduce_only_signal,
)


def test_valid_feedback_signal_can_be_created():
    signal = FeedbackSignal(
        signal_id="feedback-001",
        source_layer=FeedbackSourceLayer.DATA_QUALITY,
        target_layers=(FeedbackTargetLayer.MACRO,),
        severity=FeedbackSeverity.WARNING,
        timing=FeedbackTiming.SAME_RUN_REFINEMENT,
        as_of_date=date(2024, 3, 10),
        reason_codes=("LOW_DATA_QUALITY",),
        message="Data quality is below review threshold.",
        recommended_action="HOLD",
    )

    assert signal.signal_id == "feedback-001"
    assert signal.target_layers == (FeedbackTargetLayer.MACRO,)


def test_empty_target_layers_only_allowed_for_audit_only():
    FeedbackSignal(
        signal_id="audit-001",
        source_layer=FeedbackSourceLayer.AUDIT,
        target_layers=(),
        severity=FeedbackSeverity.INFO,
        timing=FeedbackTiming.AUDIT_ONLY,
        as_of_date=date(2024, 3, 10),
        reason_codes=("AUDIT_TRACE",),
        message="Audit-only feedback.",
    )

    with pytest.raises(FeedbackContractError):
        FeedbackSignal(
            signal_id="bad-001",
            source_layer=FeedbackSourceLayer.DATA_QUALITY,
            target_layers=(),
            severity=FeedbackSeverity.WARNING,
            timing=FeedbackTiming.SAME_RUN_REFINEMENT,
            as_of_date=date(2024, 3, 10),
            reason_codes=("MISSING_TARGET",),
            message="Missing target should fail.",
        )


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("severity", "BUY"),
        ("timing", "IMMEDIATE_EXECUTION"),
        ("source_layer", "BROKER"),
        ("target_layer", "LIVE_EXECUTION"),
    ],
)
def test_invalid_enumerated_values_fail(field_name, value):
    kwargs = {
        "signal_id": "bad-enum",
        "source_layer": FeedbackSourceLayer.DATA_QUALITY,
        "target_layers": (FeedbackTargetLayer.MACRO,),
        "severity": FeedbackSeverity.WARNING,
        "timing": FeedbackTiming.SAME_RUN_REFINEMENT,
        "as_of_date": date(2024, 3, 10),
        "reason_codes": ("BAD_ENUM",),
        "message": "Invalid enum value.",
    }
    if field_name == "target_layer":
        kwargs["target_layers"] = (value,)
    else:
        kwargs[field_name] = value

    with pytest.raises(FeedbackContractError):
        FeedbackSignal(**kwargs)


@pytest.mark.parametrize("action", ["AUTO_EXECUTE", "SUBMIT_ORDER", "BROKER_MUTATION", "INCREASE_RISK"])
def test_forbidden_recommended_actions_fail(action):
    with pytest.raises(FeedbackContractError):
        FeedbackSignal(
            signal_id="bad-action",
            source_layer=FeedbackSourceLayer.RISK_BUDGET,
            target_layers=(FeedbackTargetLayer.ALLOCATION,),
            severity=FeedbackSeverity.BLOCK,
            timing=FeedbackTiming.SAME_RUN_REFINEMENT,
            as_of_date=date(2024, 3, 10),
            reason_codes=("FORBIDDEN_ACTION",),
            message="Forbidden action should fail.",
            recommended_action=action,
        )


def test_non_conservative_recommended_action_fails():
    with pytest.raises(FeedbackContractError):
        FeedbackSignal(
            signal_id="buy-action",
            source_layer=FeedbackSourceLayer.REBALANCING,
            target_layers=(FeedbackTargetLayer.ORDER_CANDIDATE,),
            severity=FeedbackSeverity.INFO,
            timing=FeedbackTiming.NEXT_RUN_INPUT,
            as_of_date=date(2024, 3, 10),
            reason_codes=("BUY_NOT_ALLOWED",),
            message="Buy action should not be a feedback recommendation.",
            recommended_action="BUY",
        )


def test_risk_reduce_only_signal_uses_conservative_action():
    signal = risk_reduce_only_signal(
        signal_id="risk-reduce",
        source_layer=FeedbackSourceLayer.RISK_BUDGET,
        target_layers=(FeedbackTargetLayer.ALLOCATION, FeedbackTargetLayer.REBALANCING),
        as_of_date=date(2024, 3, 10),
        reason_codes=("RISK_LIMIT",),
        message="Risk limit requires reduce-only handling.",
    )

    assert signal.severity == FeedbackSeverity.REDUCE_ONLY
    assert signal.recommended_action == "RISK_REDUCE_ONLY"


def test_decision_feedback_domain_module_stays_pure():
    path = Path("api/domain/decision_feedback.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"fastapi", "starlette", "sqlite3", "api.db", "api.features"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)
