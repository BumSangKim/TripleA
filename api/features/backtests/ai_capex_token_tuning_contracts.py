from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from typing import Any, Mapping


class AICapexTokenTuningContractError(ValueError):
    pass


TUNING_STATUSES = {
    "PASS_SYNTHETIC_ONLY",
    "PASS_HISTORICAL_DIAGNOSTIC",
    "REVIEW_REQUIRED",
    "FAIL_NOOP_TUNING",
    "FAIL_STATIC_MARKET_MAPPING",
    "FAIL_LEAKAGE_RISK",
}


@dataclass(frozen=True)
class TuningCandidate:
    candidate_id: str
    parameters: Mapping[str, Any]
    parameter_hash: str
    parameter_version: str
    diagnostic_only: bool = True

    def __post_init__(self) -> None:
        _require_text(self.candidate_id, "candidate_id")
        if not isinstance(self.parameters, Mapping):
            raise AICapexTokenTuningContractError("parameters must be a mapping")
        _require_text(self.parameter_hash, "parameter_hash")
        expected_hash = deterministic_hash(self.parameters)
        if self.parameter_hash != expected_hash:
            raise AICapexTokenTuningContractError("parameter_hash must match deterministic parameter payload hash")
        _require_text(self.parameter_version, "parameter_version")
        if self.diagnostic_only is not True:
            raise AICapexTokenTuningContractError("tuning candidate must remain diagnostic_only")

    @classmethod
    def from_parameters(
        cls,
        *,
        candidate_id: str,
        parameters: Mapping[str, Any],
        parameter_version: str,
        diagnostic_only: bool = True,
    ) -> TuningCandidate:
        return cls(
            candidate_id=candidate_id,
            parameters=dict(parameters),
            parameter_hash=deterministic_hash(parameters),
            parameter_version=parameter_version,
            diagnostic_only=diagnostic_only,
        )

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


@dataclass(frozen=True)
class TuningCandidateResult:
    candidate: TuningCandidate
    metrics: Mapping[str, Any]
    output_signature: str
    metric_signature: str
    objective_score: float
    rejected: bool = False
    reject_reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, TuningCandidate):
            raise AICapexTokenTuningContractError("candidate must be a TuningCandidate")
        if not isinstance(self.metrics, Mapping):
            raise AICapexTokenTuningContractError("metrics must be a mapping")
        _require_text(self.output_signature, "output_signature")
        _require_text(self.metric_signature, "metric_signature")
        float(self.objective_score)
        _coerce_text_tuple(self, "reject_reasons")
        if self.rejected and not self.reject_reasons:
            raise AICapexTokenTuningContractError("rejected candidate requires reject_reasons")

    @classmethod
    def from_payloads(
        cls,
        *,
        candidate: TuningCandidate,
        output_payload: Mapping[str, Any],
        metrics: Mapping[str, Any],
        objective_score: float,
        rejected: bool = False,
        reject_reasons: tuple[str, ...] = (),
    ) -> TuningCandidateResult:
        return cls(
            candidate=candidate,
            metrics=dict(metrics),
            output_signature=deterministic_hash(output_payload),
            metric_signature=deterministic_hash(metrics),
            objective_score=float(objective_score),
            rejected=rejected,
            reject_reasons=reject_reasons,
        )

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(asdict(self))


@dataclass(frozen=True)
class TuningExecutionValidationResult:
    status: str
    candidates: tuple[TuningCandidateResult, ...]
    selected_candidate_id: str | None
    memory_cycle_coverage: Mapping[str, Any]
    leakage_check_passed: bool
    no_op_tuning_detected: bool
    diagnostic_only: bool = True
    production_ready: bool = False

    def __post_init__(self) -> None:
        if self.status not in TUNING_STATUSES:
            raise AICapexTokenTuningContractError("unsupported tuning validation status")
        _coerce_tuple(self, "candidates")
        if self.selected_candidate_id is not None:
            _require_text(self.selected_candidate_id, "selected_candidate_id")
        if not isinstance(self.memory_cycle_coverage, Mapping):
            raise AICapexTokenTuningContractError("memory_cycle_coverage must be a mapping")
        if self.diagnostic_only is not True:
            raise AICapexTokenTuningContractError("validation result must remain diagnostic_only")
        if self.production_ready is not False:
            raise AICapexTokenTuningContractError("validation result must not be production_ready")
        if len(self.candidates) < 2 and self.status not in {"FAIL_NOOP_TUNING", "REVIEW_REQUIRED"}:
            raise AICapexTokenTuningContractError("candidate_count < 2 must be no-op or review")
        if self.no_op_tuning_detected and self.status != "FAIL_NOOP_TUNING":
            raise AICapexTokenTuningContractError("no_op_tuning_detected requires FAIL_NOOP_TUNING")
        if not self.leakage_check_passed and self.status != "FAIL_LEAKAGE_RISK":
            raise AICapexTokenTuningContractError("failed leakage check requires FAIL_LEAKAGE_RISK")

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def unique_parameter_hash_count(self) -> int:
        return len({result.candidate.parameter_hash for result in self.candidates})

    @property
    def unique_output_signature_count(self) -> int:
        return len({result.output_signature for result in self.candidates})

    @property
    def unique_metric_signature_count(self) -> int:
        return len({result.metric_signature for result in self.candidates})

    @classmethod
    def from_candidate_results(
        cls,
        *,
        candidates: tuple[TuningCandidateResult, ...],
        selected_candidate_id: str | None,
        memory_cycle_coverage: Mapping[str, Any],
        leakage_check_passed: bool,
        diagnostic_only: bool = True,
        production_ready: bool = False,
        historical_cycle_passed: bool = False,
    ) -> TuningExecutionValidationResult:
        unique_output = len({result.output_signature for result in candidates})
        unique_metrics = len({result.metric_signature for result in candidates})
        no_op = len(candidates) < 2 or unique_output < 2 or unique_metrics < 2
        if not leakage_check_passed:
            status = "FAIL_LEAKAGE_RISK"
        elif no_op:
            status = "FAIL_NOOP_TUNING"
        elif historical_cycle_passed:
            status = "PASS_HISTORICAL_DIAGNOSTIC"
        else:
            status = "PASS_SYNTHETIC_ONLY"
        return cls(
            status=status,
            candidates=candidates,
            selected_candidate_id=selected_candidate_id,
            memory_cycle_coverage=dict(memory_cycle_coverage),
            leakage_check_passed=leakage_check_passed,
            no_op_tuning_detected=no_op,
            diagnostic_only=diagnostic_only,
            production_ready=production_ready,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = _to_jsonable(asdict(self))
        payload.update(
            {
                "candidate_count": self.candidate_count,
                "unique_parameter_hash_count": self.unique_parameter_hash_count,
                "unique_output_signature_count": self.unique_output_signature_count,
                "unique_metric_signature_count": self.unique_metric_signature_count,
            }
        )
        return payload


def deterministic_hash(payload: Any) -> str:
    serialized = deterministic_json(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def deterministic_json(payload: Any) -> str:
    return json.dumps(_to_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, tuple | list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AICapexTokenTuningContractError(f"{field_name} must be a non-empty string")


def _coerce_tuple(instance: Any, field_name: str) -> None:
    value = getattr(instance, field_name)
    if not isinstance(value, tuple):
        object.__setattr__(instance, field_name, tuple(value))


def _coerce_text_tuple(instance: Any, field_name: str) -> None:
    _coerce_tuple(instance, field_name)
    for item in getattr(instance, field_name):
        _require_text(item, field_name)
