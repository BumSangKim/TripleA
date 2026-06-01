from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Mapping

from api.domain.scoring.ai_capex_token_contracts import (
    AICapexTokenMetric,
    AICapexTokenRawSnapshot,
    CAPEX_PERIOD_ROLES,
    TOKEN_CURRENT_PERIOD_ROLE,
    TOKEN_PREVIOUS_PERIOD_ROLE,
)
from api.plugin_boundary import time_guard


class AICapexTokenInputAdapterError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        reason_codes: tuple[str, ...],
        fallback_state: str = "REVIEW_REQUIRED",
        excluded_metric_keys: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.reason_codes = reason_codes
        self.fallback_state = fallback_state
        self.excluded_metric_keys = excluded_metric_keys


@dataclass(frozen=True)
class AICapexTokenInputAdapterResult:
    snapshot: AICapexTokenRawSnapshot | None
    reason_codes: tuple[str, ...] = ()
    fallback_state: str | None = None
    excluded_metric_keys: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


class AICapexTokenInputAdapter:
    def adapt(self, payload: Mapping[str, Any] | object) -> AICapexTokenRawSnapshot:
        result = self.adapt_with_metadata(payload)
        if result.snapshot is None:
            raise AICapexTokenInputAdapterError(
                "AI Capex-Token input is not complete enough for scoring",
                reason_codes=result.reason_codes,
                fallback_state=result.fallback_state or "REVIEW_REQUIRED",
                excluded_metric_keys=result.excluded_metric_keys,
            )
        return result.snapshot

    def adapt_with_metadata(self, payload: Mapping[str, Any] | object) -> AICapexTokenInputAdapterResult:
        data = _as_mapping(payload)
        decision_date = _parse_date(data["decision_date"])
        decision_time = datetime.combine(decision_date, time.max)
        excluded: list[str] = []
        invalid: list[str] = []
        reason_codes: list[str] = []

        current = _available_metrics(data.get("token_sources_current", ()), decision_time, excluded, invalid)
        previous = _available_metrics(data.get("token_sources_previous", ()), decision_time, excluded, invalid)
        capex = _available_metrics(data.get("capex_series", ()), decision_time, excluded, invalid)

        current = tuple(metric for metric in current if metric.period_role == TOKEN_CURRENT_PERIOD_ROLE)
        previous = tuple(metric for metric in previous if metric.period_role == TOKEN_PREVIOUS_PERIOD_ROLE)
        capex = tuple(metric for metric in capex if metric.period_role in CAPEX_PERIOD_ROLES)

        if excluded:
            reason_codes.append("FUTURE_INPUT_EXCLUDED")
        if invalid:
            reason_codes.append("INVALID_EXPLICIT_PERIOD_ROLE_REVIEW_REQUIRED")
        if not current:
            reason_codes.append("MISSING_TOKEN_CURRENT_REVIEW_REQUIRED")
        if not previous:
            reason_codes.append("MISSING_TOKEN_PREVIOUS_REVIEW_REQUIRED")
        missing_capex = CAPEX_PERIOD_ROLES - {metric.period_role for metric in capex}
        if missing_capex:
            reason_codes.append("MISSING_CAPEX_PERIOD_REVIEW_REQUIRED")
        if _has_low_quality([*current, *previous, *capex]):
            reason_codes.append("LOW_DATA_QUALITY_REVIEW_REQUIRED")

        if invalid or not current or not previous or missing_capex:
            return AICapexTokenInputAdapterResult(
                snapshot=None,
                reason_codes=tuple(reason_codes),
                fallback_state="REVIEW_REQUIRED",
                excluded_metric_keys=tuple(excluded),
                metadata={"diagnostic_only": True, "invalid_metric_keys": tuple(invalid)},
            )

        snapshot = AICapexTokenRawSnapshot(
            snapshot_id=str(data["snapshot_id"]),
            decision_date=decision_date,
            token_sources_current=current,
            token_sources_previous=previous,
            capex_series=capex,
            sector_metrics=data.get("sector_metrics") or {},
            macro_overlay_metrics=data.get("macro_overlay_metrics") or {},
            metadata={
                **dict(data.get("metadata") or {}),
                "reason_codes": tuple(reason_codes),
                "excluded_metric_keys": tuple(excluded),
                "diagnostic_only": True,
            },
        )
        return AICapexTokenInputAdapterResult(
            snapshot=snapshot,
            reason_codes=tuple(reason_codes),
            excluded_metric_keys=tuple(excluded),
            metadata=snapshot.metadata,
        )


def adapt_ai_capex_token_input(payload: Mapping[str, Any] | object) -> AICapexTokenRawSnapshot:
    return AICapexTokenInputAdapter().adapt(payload)


def _available_metrics(
    rows: Any,
    decision_time: datetime,
    excluded: list[str],
    invalid: list[str],
) -> tuple[AICapexTokenMetric, ...]:
    metrics: list[AICapexTokenMetric] = []
    for row in rows or ():
        try:
            metrics.append(_metric_from_row(row))
        except (KeyError, TypeError, ValueError) as exc:
            data = _as_mapping(row)
            invalid.append(str(data.get("metric_key") or data.get("source") or exc))
    available: list[AICapexTokenMetric] = []
    for metric in metrics:
        if time_guard.is_available_for_decision(metric, decision_time):
            available.append(metric)
        else:
            excluded.append(metric.metric_key)
    return tuple(available)


def _metric_from_row(row: Mapping[str, Any] | object) -> AICapexTokenMetric:
    data = _as_mapping(row)
    return AICapexTokenMetric(
        metric_key=str(data["metric_key"]),
        period_role=str(data["period_role"]),
        value=float(data["value"]),
        as_of_date=_parse_date(data["as_of_date"]),
        available_at=_parse_datetime(data["available_at"]),
        source=str(data["source"]),
        quality_score=float(data["quality_score"]),
        missing_ratio=float(data.get("missing_ratio", 0.0)),
        is_stale=bool(data.get("is_stale", False)),
        metadata=data.get("metadata") or {},
    )


def _as_mapping(value: Mapping[str, Any] | object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    data = getattr(value, "data", None)
    if isinstance(data, Mapping):
        return data
    if hasattr(value, "__dict__"):
        return vars(value)
    raise AICapexTokenInputAdapterError(
        "unsupported AI Capex-Token input payload",
        reason_codes=("UNSUPPORTED_INPUT_PAYLOAD",),
    )


def _parse_date(value: str | date) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _has_low_quality(metrics: list[AICapexTokenMetric]) -> bool:
    return any(metric.quality_score < 0.5 or metric.missing_ratio > 0.5 or metric.is_stale for metric in metrics)
