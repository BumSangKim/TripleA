from __future__ import annotations

from datetime import date
from typing import Any

from api.domain.decision_feedback import (
    FeedbackSignal,
    FeedbackSourceLayer,
    FeedbackTargetLayer,
    block_signal,
    review_required_signal,
    risk_reduce_only_signal,
)


class FeedbackCollector:
    """Collect review-only feedback from score-flow output contracts."""

    def collect(self, *outputs: Any, as_of_date: date) -> tuple[FeedbackSignal, ...]:
        signals: list[FeedbackSignal] = []
        for output in outputs:
            signals.extend(self._collect_from_output(output, as_of_date=as_of_date))
        return tuple(signals)

    def _collect_from_output(self, output: Any, *, as_of_date: date) -> tuple[FeedbackSignal, ...]:
        if output is None:
            return ()
        if _is_blocked_constraint(output):
            return (self._blocked_constraint_signal(output, as_of_date=as_of_date),)
        if hasattr(output, "constraint_result") and _is_blocked_constraint(output.constraint_result):
            return (self._blocked_constraint_signal(output.constraint_result, as_of_date=as_of_date),)
        if _looks_like_warning(output):
            signal = self._signal_from_warning(output, as_of_date=as_of_date)
            return (signal,) if signal is not None else ()

        signals: list[FeedbackSignal] = []
        for warning in getattr(output, "warnings", ()) or ():
            signal = self._signal_from_warning(warning, as_of_date=as_of_date)
            if signal is not None:
                signals.append(signal)
        return tuple(signals)

    def _blocked_constraint_signal(self, output: Any, *, as_of_date: date) -> FeedbackSignal:
        reason_codes = _reason_codes_from(output) or ("CONSTRAINT_BLOCKED",)
        conservative_action = getattr(output, "conservative_action", None)
        if conservative_action == "RISK_REDUCE_ONLY":
            return risk_reduce_only_signal(
                signal_id=_signal_id("risk-reduce-only", reason_codes),
                source_layer=FeedbackSourceLayer.ACCOUNT_CONSTRAINT,
                target_layers=(FeedbackTargetLayer.ALLOCATION, FeedbackTargetLayer.REBALANCING),
                as_of_date=as_of_date,
                reason_codes=reason_codes,
                message="Constraint result requires risk-reduce-only handling.",
            )
        return block_signal(
            signal_id=_signal_id("constraint-blocked", reason_codes),
            source_layer=FeedbackSourceLayer.ACCOUNT_CONSTRAINT,
            target_layers=(FeedbackTargetLayer.ALLOCATION, FeedbackTargetLayer.REBALANCING),
            as_of_date=as_of_date,
            reason_codes=reason_codes,
            message="Constraint result is blocked and requires review.",
        )

    def _signal_from_warning(self, warning: Any, *, as_of_date: date) -> FeedbackSignal | None:
        severity = str(getattr(warning, "severity", "") or "")
        code = str(getattr(warning, "code", "") or "WARNING")
        message = str(getattr(warning, "message", "") or code)
        source = str(getattr(warning, "source", "") or "")
        reason_codes = (code,)
        if severity == "BLOCKER":
            return block_signal(
                signal_id=_signal_id("warning-blocker", reason_codes),
                source_layer=_source_layer_from_warning_source(source),
                target_layers=(FeedbackTargetLayer.ALLOCATION, FeedbackTargetLayer.REBALANCING),
                as_of_date=as_of_date,
                reason_codes=reason_codes,
                message=message,
            )
        if "LOW_DATA_QUALITY" in code or "DATA_QUALITY" in code or "data quality" in message.lower():
            return review_required_signal(
                signal_id=_signal_id("warning-review", reason_codes),
                source_layer=FeedbackSourceLayer.DATA_QUALITY,
                target_layers=(FeedbackTargetLayer.MACRO, FeedbackTargetLayer.ALLOCATION),
                as_of_date=as_of_date,
                reason_codes=reason_codes,
                message=message,
            )
        return None


def _is_blocked_constraint(output: Any) -> bool:
    return bool(getattr(output, "blocked", False))


def _looks_like_warning(output: Any) -> bool:
    return hasattr(output, "severity") and hasattr(output, "code")


def _reason_codes_from(output: Any) -> tuple[str, ...]:
    values = []
    for reason in getattr(output, "reason_codes", ()) or ():
        code = getattr(reason, "code", None)
        values.append(str(code or reason))
    return tuple(value for value in values if value)


def _source_layer_from_warning_source(source: str) -> str:
    normalized = source.upper()
    if "RISK" in normalized:
        return FeedbackSourceLayer.RISK_BUDGET
    if "REBALANC" in normalized:
        return FeedbackSourceLayer.REBALANCING
    if "CONSTRAINT" in normalized or "ACCOUNT" in normalized:
        return FeedbackSourceLayer.ACCOUNT_CONSTRAINT
    if "BACKTEST" in normalized:
        return FeedbackSourceLayer.BACKTEST
    if "AUDIT" in normalized:
        return FeedbackSourceLayer.AUDIT
    return FeedbackSourceLayer.DATA_QUALITY


def _signal_id(prefix: str, reason_codes: tuple[str, ...]) -> str:
    reason = reason_codes[0].lower().replace("_", "-") if reason_codes else "review"
    return f"{prefix}-{reason}"
