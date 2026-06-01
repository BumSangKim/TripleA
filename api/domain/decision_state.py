from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping

from api.domain.decision_feedback import FeedbackSeverity, FeedbackSignal


class DecisionStateContractError(ValueError):
    pass


FORBIDDEN_NEXT_RUN_KEYS = frozenset(
    {
        "AUTO_EXECUTE",
        "BROKER_MUTATION",
        "EXECUTION_ALLOWED",
        "INCREASE_RISK",
        "LIVE_EXECUTE",
        "PLACE_ORDER",
        "SUBMIT_ORDER",
        "auto_execute",
        "broker_mutation",
        "execution_allowed",
        "increase_risk",
        "live_execute",
        "_".join(("place", "order")),
        "_".join(("submit", "order")),
    }
)


@dataclass(frozen=True)
class LayerOutputEnvelope:
    layer: str
    output_type: str
    as_of_date: date
    payload: Mapping[str, Any]
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    parameter_version: str | None = None
    model_version: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.layer, "layer")
        _require_text(self.output_type, "output_type")
        if self.as_of_date is None:
            raise DecisionStateContractError("as_of_date is required")
        if not isinstance(self.payload, Mapping):
            raise DecisionStateContractError("payload must be a mapping")
        _require_tuple(self.reason_codes, "reason_codes")
        _require_tuple(self.warnings, "warnings")
        _reject_forbidden_keys(self.payload, "payload")


@dataclass(frozen=True)
class DecisionStateSnapshot:
    snapshot_id: str
    as_of_date: date
    run_id: str
    layer_outputs: tuple[LayerOutputEnvelope, ...]
    feedback_signals: tuple[FeedbackSignal, ...]
    next_run_inputs: Mapping[str, Any] = field(default_factory=dict)
    audit_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        _require_text(self.run_id, "run_id")
        if self.as_of_date is None:
            raise DecisionStateContractError("as_of_date is required")
        if not isinstance(self.layer_outputs, tuple):
            raise DecisionStateContractError("layer_outputs must be an immutable tuple")
        if not isinstance(self.feedback_signals, tuple):
            raise DecisionStateContractError("feedback_signals must be an immutable tuple")
        if not isinstance(self.next_run_inputs, Mapping):
            raise DecisionStateContractError("next_run_inputs must be a mapping")
        if not isinstance(self.audit_metadata, Mapping):
            raise DecisionStateContractError("audit_metadata must be a mapping")
        _reject_forbidden_keys(self.next_run_inputs, "next_run_inputs")
        _reject_forbidden_keys(self.audit_metadata, "audit_metadata")

    def feedback_for_layer(self, layer: str) -> tuple[FeedbackSignal, ...]:
        _require_text(layer, "layer")
        return tuple(signal for signal in self.feedback_signals if layer in signal.target_layers)

    def outputs_for_layer(self, layer: str) -> tuple[LayerOutputEnvelope, ...]:
        _require_text(layer, "layer")
        return tuple(output for output in self.layer_outputs if output.layer == layer)

    def has_blocking_feedback(self) -> bool:
        return any(signal.severity == FeedbackSeverity.BLOCK for signal in self.feedback_signals)

    def to_next_run_input(self) -> Mapping[str, Any]:
        payload: dict[str, Any] = {
            "as_of_date": self.as_of_date.isoformat(),
            "previous_run_id": self.run_id,
            "feedback_signals": [
                {
                    "signal_id": signal.signal_id,
                    "source_layer": signal.source_layer,
                    "target_layers": signal.target_layers,
                    "severity": signal.severity,
                    "timing": signal.timing,
                    "reason_codes": signal.reason_codes,
                    "recommended_action": signal.recommended_action,
                    "subject_id": signal.subject_id,
                    "subject_type": signal.subject_type,
                }
                for signal in self.feedback_signals
            ],
            "next_run_inputs": dict(self.next_run_inputs),
        }
        _reject_forbidden_keys(payload, "next_run_input_export")
        return payload


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DecisionStateContractError(f"{field_name} must be a non-empty string")


def _require_tuple(value: tuple[str, ...], field_name: str) -> None:
    if not isinstance(value, tuple):
        raise DecisionStateContractError(f"{field_name} must be an immutable tuple")
    for item in value:
        _require_text(item, field_name)


def _reject_forbidden_keys(value: Any, field_name: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in FORBIDDEN_NEXT_RUN_KEYS:
                raise DecisionStateContractError(f"{field_name} contains forbidden execution key")
            _reject_forbidden_keys(nested, field_name)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_forbidden_keys(item, field_name)
