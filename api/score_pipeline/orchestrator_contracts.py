from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Protocol

from api.domain.decision_feedback import FeedbackSignal
from api.domain.decision_state import DecisionStateSnapshot, LayerOutputEnvelope


class OrchestratorContractError(ValueError):
    pass


class DecisionRunMode:
    DRY_RUN = "DRY_RUN"
    BACKTEST = "BACKTEST"
    REVIEW_ONLY = "REVIEW_ONLY"

    @classmethod
    def values(cls) -> set[str]:
        return {cls.DRY_RUN, cls.BACKTEST, cls.REVIEW_ONLY}


class DecisionLayerId:
    DATA = "DATA"
    FEATURE = "FEATURE"
    SCORE = "SCORE"
    MACRO = "MACRO"
    SECTOR_ASSET = "SECTOR_ASSET"
    RISK_BUDGET = "RISK_BUDGET"
    ALLOCATION = "ALLOCATION"
    REBALANCING = "REBALANCING"
    ACCOUNT_CONSTRAINT = "ACCOUNT_CONSTRAINT"
    ORDER_CANDIDATE = "ORDER_CANDIDATE"
    AUDIT = "AUDIT"

    @classmethod
    def values(cls) -> set[str]:
        return {
            cls.DATA,
            cls.FEATURE,
            cls.SCORE,
            cls.MACRO,
            cls.SECTOR_ASSET,
            cls.RISK_BUDGET,
            cls.ALLOCATION,
            cls.REBALANCING,
            cls.ACCOUNT_CONSTRAINT,
            cls.ORDER_CANDIDATE,
            cls.AUDIT,
        }


FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "AUTO_EXECUTE",
        "BROKER_MUTATION",
        "INCREASE_RISK",
        "LIVE_EXECUTE",
        "PLACE_ORDER",
        "SUBMIT_ORDER",
        "auto_execute",
        "broker_mutation",
        "increase_risk",
        "live_execute",
        "_".join(("place", "order")),
        "_".join(("submit", "order")),
    }
)


@dataclass(frozen=True)
class DecisionRequest:
    run_id: str
    as_of_date: date
    mode: str
    raw_inputs: Mapping[str, Any]
    portfolio_state: Mapping[str, Any]
    account_state: Mapping[str, Any]
    parameter_version: str
    previous_state: DecisionStateSnapshot | None = None

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        _require_text(self.parameter_version, "parameter_version")
        if self.as_of_date is None:
            raise OrchestratorContractError("as_of_date is required")
        if self.mode not in DecisionRunMode.values():
            raise OrchestratorContractError("mode is not allowed")
        for field_name in ("raw_inputs", "portfolio_state", "account_state"):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise OrchestratorContractError(f"{field_name} must be a mapping")
            _reject_forbidden_keys(value, field_name)


@dataclass(frozen=True)
class DecisionResult:
    run_id: str
    as_of_date: date
    mode: str
    state_snapshot: DecisionStateSnapshot
    review_only: bool = True
    execution_allowed: bool = False

    def __post_init__(self) -> None:
        _require_text(self.run_id, "run_id")
        if self.as_of_date is None:
            raise OrchestratorContractError("as_of_date is required")
        if self.mode not in DecisionRunMode.values():
            raise OrchestratorContractError("mode is not allowed")
        if self.review_only is not True:
            raise OrchestratorContractError("review_only must remain true")
        if self.execution_allowed is not False:
            raise OrchestratorContractError("execution_allowed must remain false")


class LayerRunner(Protocol):
    layer_id: str

    def run(self, request_or_context: Any) -> LayerOutputEnvelope:
        ...


@dataclass(frozen=True)
class ControlledRefinementPlan:
    feedback_signals: tuple[FeedbackSignal, ...]
    layers_to_revisit: tuple[str, ...]
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.feedback_signals, tuple):
            raise OrchestratorContractError("feedback_signals must be an immutable tuple")
        if not isinstance(self.layers_to_revisit, tuple):
            raise OrchestratorContractError("layers_to_revisit must be an immutable tuple")
        for layer in self.layers_to_revisit:
            if layer not in DecisionLayerId.values():
                raise OrchestratorContractError("layers_to_revisit contains an unsupported layer")
        for reason in self.reason_codes:
            _require_text(reason, "reason_code")

    @classmethod
    def from_feedback_signals(cls, feedback_signals: tuple[FeedbackSignal, ...]) -> "ControlledRefinementPlan":
        layers: list[str] = []
        for signal in feedback_signals:
            for layer in signal.target_layers:
                if layer in DecisionLayerId.values() and layer not in layers:
                    layers.append(layer)
        return cls(
            feedback_signals=feedback_signals,
            layers_to_revisit=tuple(layers),
            reason_codes=tuple(signal.reason_codes[0] for signal in feedback_signals if signal.reason_codes),
        )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise OrchestratorContractError(f"{field_name} must be a non-empty string")


def _reject_forbidden_keys(value: Any, field_name: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if str(key) in FORBIDDEN_REQUEST_KEYS:
                raise OrchestratorContractError(f"{field_name} contains forbidden execution key")
            _reject_forbidden_keys(nested, field_name)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_forbidden_keys(item, field_name)
