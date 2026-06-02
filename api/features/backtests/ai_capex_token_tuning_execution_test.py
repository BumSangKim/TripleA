from __future__ import annotations

from dataclasses import asdict
from statistics import pstdev
from typing import Any, Mapping, Sequence

from api.features.backtests.ai_capex_token_memory_cycle_gate import validate_two_memory_cycle_coverage
from api.features.backtests.ai_capex_token_tuning_contracts import (
    TuningCandidate,
    TuningCandidateResult,
    TuningExecutionValidationResult,
)
from api.strategy.ai_capex_token_component import AICapexTokenDiagnosticComponent
from api.strategy.ai_capex_token_input_adapter import AICapexTokenInputAdapter


def run_ai_capex_token_tuning_execution_test(
    *,
    candidate_grid: Mapping[str, Any],
    snapshots: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    candidates = _load_candidates(candidate_grid)
    coverage = validate_two_memory_cycle_coverage(snapshots)
    raw_results = tuple(_evaluate_candidate(candidate, snapshots) for candidate in candidates)
    results = _apply_rejection_rules(raw_results)
    selected = _select_candidate_id(results)
    validation = TuningExecutionValidationResult.from_candidate_results(
        candidates=results,
        selected_candidate_id=selected,
        memory_cycle_coverage=coverage.to_dict(),
        leakage_check_passed=_leakage_check_passed(results),
        historical_cycle_passed=False,
    )
    payload = validation.to_dict()
    payload.update(
        {
            "baseline_candidate_id": candidates[0].candidate_id if candidates else None,
            "objective_breakdown": {
                result.candidate.candidate_id: dict(result.metrics.get("objective_components", {}))
                for result in results
            },
            "rejected_candidates": [
                {
                    "candidate_id": result.candidate.candidate_id,
                    "reject_reasons": list(result.reject_reasons),
                }
                for result in results
                if result.rejected
            ],
            "candidate_parameter_projection": {
                "scenario_smoothing_alpha": "scenario_probability_parameters.membership_strength"
            },
            "leakage_warnings": _leakage_warnings(results),
        }
    )
    return payload


def _load_candidates(candidate_grid: Mapping[str, Any]) -> tuple[TuningCandidate, ...]:
    candidates: list[TuningCandidate] = []
    for row in candidate_grid.get("candidates", ()):
        if not isinstance(row, Mapping):
            continue
        candidates.append(
            TuningCandidate.from_parameters(
                candidate_id=str(row["candidate_id"]),
                parameters=dict(row.get("parameters") or {}),
                parameter_version=str(row.get("parameter_version") or "ai_capex_token_tuning_execution_unversioned"),
                diagnostic_only=bool(row.get("diagnostic_only", True)),
            )
        )
    return tuple(candidates)


def _evaluate_candidate(candidate: TuningCandidate, snapshots: Sequence[Mapping[str, Any]]) -> TuningCandidateResult:
    config = _candidate_config(candidate)
    rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        rows.append(_evaluate_snapshot(snapshot, config))
    metrics = _metrics(candidate, rows)
    return TuningCandidateResult.from_payloads(
        candidate=candidate,
        output_payload={"rows": _available_output_rows(rows)},
        metrics=metrics,
        objective_score=float(metrics["objective_score"]),
    )


def _evaluate_snapshot(snapshot: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    adapter_result = AICapexTokenInputAdapter().adapt_with_metadata(snapshot)
    if adapter_result.snapshot is None:
        return {
            "snapshot_id": str(snapshot.get("snapshot_id", "unknown")),
            "status": adapter_result.fallback_state or "REVIEW_REQUIRED",
            "diagnostic_only": True,
            "component_count": 0,
            "component_scores": {},
            "component_confidences": {},
            "dominant_scenario": None,
            "scenario_probabilities": {},
            "reason_codes": list(adapter_result.reason_codes),
            "excluded_metric_keys": list(adapter_result.excluded_metric_keys),
        }
    diagnostic = AICapexTokenDiagnosticComponent().build(snapshot, config=config)
    components = diagnostic.components
    dominant = components[0].scenario_distribution.dominant_scenario if components else None
    probabilities = dict(components[0].scenario_distribution.probabilities) if components else {}
    reason_codes = _unique(
        [
            *diagnostic.reason_codes,
            *(code for component in components for code in component.reason_codes),
            *adapter_result.reason_codes,
        ]
    )
    return {
        "snapshot_id": adapter_result.snapshot.snapshot_id,
        "status": "DIAGNOSTIC_ONLY",
        "diagnostic_only": bool(diagnostic.diagnostic_only),
        "component_count": len(components),
        "component_scores": {component.sector_id: component.component_score for component in components},
        "component_confidences": {component.sector_id: component.confidence for component in components},
        "dominant_scenario": dominant,
        "scenario_probabilities": probabilities,
        "reason_codes": reason_codes,
        "excluded_metric_keys": list(adapter_result.excluded_metric_keys),
        "macro_overlay": dict(diagnostic.metadata.get("macro_overlay", {})),
        "component_payloads": [asdict(component) for component in components],
    }


def _candidate_config(candidate: TuningCandidate) -> dict[str, Any]:
    membership_strength = _required_ratio(candidate.parameters, "scenario_smoothing_alpha")
    return {
        "enabled": False,
        "diagnostic_only": True,
        "normalization_parameters": {"metadata": {"approved": True}},
        "scenario_probability_parameters": {"membership_strength": membership_strength},
        "parameter_metadata": {
            "parameter_version": candidate.parameter_version,
            "approved": False,
            "production_enabled": False,
        },
    }


def _metrics(candidate: TuningCandidate, rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    component_scores = [
        float(score)
        for row in rows
        for score in (row.get("component_scores") or {}).values()
    ]
    confidences = [
        float(confidence)
        for row in rows
        for confidence in (row.get("component_confidences") or {}).values()
    ]
    avg_score = sum(component_scores) / len(component_scores) if component_scores else 0.0
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    score_stability = max(0.0, 1.0 - pstdev(component_scores)) if len(component_scores) > 1 else 0.0
    turnover_penalty = _ratio(candidate.parameters.get("turnover_penalty", 1.0), default=1.0)
    turnover_efficiency = max(0.0, 1.0 - turnover_penalty)
    reason_code_count = len(_objective_reason_codes(rows))
    excluded_metric_keys = sorted({key for row in rows for key in row.get("excluded_metric_keys", ())})
    explainability = min(1.0, reason_code_count / 10.0)
    penalties = {
        "turnover_penalty": turnover_penalty,
        "mdd_worsening_penalty": _ratio(candidate.parameters.get("diagnostic_mdd_worsening", 0.0), default=0.0),
        "one_cycle_only_penalty": _one_cycle_only_penalty(candidate.parameters),
        "missing_output_penalty": 0.25 if not component_scores else 0.0,
        "cagr_only_penalty": 0.0,
    }
    objective_components = {
        "mdd_improvement": None,
        "risk_adjusted_return": avg_score * avg_confidence,
        "turnover_efficiency": turnover_efficiency,
        "cycle_stability": score_stability,
        "parameter_robustness": 1.0,
        "explainability": explainability,
        "penalties": penalties,
    }
    objective_score = (
        float(objective_components["risk_adjusted_return"])
        + turnover_efficiency
        + score_stability
        + explainability
        + float(objective_components["parameter_robustness"])
        - sum(float(value) for value in penalties.values())
    )
    return {
        "average_component_score": avg_score,
        "average_confidence": avg_confidence,
        "component_score_stability": score_stability,
        "excluded_metric_keys": excluded_metric_keys,
        "objective_components": objective_components,
        "objective_score": objective_score,
    }


def _select_candidate_id(results: Sequence[TuningCandidateResult]) -> str | None:
    available = [result for result in results if not result.rejected]
    if not available:
        return None
    return max(available, key=lambda result: (result.objective_score, result.candidate.candidate_id)).candidate.candidate_id


def _apply_rejection_rules(results: Sequence[TuningCandidateResult]) -> tuple[TuningCandidateResult, ...]:
    if not results:
        return ()
    baseline = next((result for result in results if result.candidate.candidate_id == "baseline"), results[0])
    rejected: list[TuningCandidateResult] = []
    seen_outputs: set[str] = set()
    for result in results:
        reject_reasons: list[str] = []
        if result.output_signature in seen_outputs:
            reject_reasons.append("NO_OUTPUT_VARIATION")
        seen_outputs.add(result.output_signature)
        if _penalty_value(result, "mdd_worsening_penalty") > 0:
            reject_reasons.append("MDD_WORSENING_DIAGNOSTIC_PENALTY")
        if _penalty_value(result, "one_cycle_only_penalty") > 0:
            reject_reasons.append("ONE_CYCLE_ONLY_DIAGNOSTIC_PENALTY")
        if result.candidate.candidate_id != baseline.candidate.candidate_id and result.objective_score < baseline.objective_score:
            reject_reasons.append("OBJECTIVE_BELOW_BASELINE_DIAGNOSTIC_REJECTED")
        if reject_reasons:
            rejected.append(
                TuningCandidateResult(
                    candidate=result.candidate,
                    metrics=result.metrics,
                    output_signature=result.output_signature,
                    metric_signature=result.metric_signature,
                    objective_score=result.objective_score,
                    rejected=True,
                    reject_reasons=tuple(reject_reasons),
                )
            )
        else:
            rejected.append(result)
    return tuple(rejected)


def _leakage_check_passed(results: Sequence[TuningCandidateResult]) -> bool:
    return any(
        "future.leakage_probe" in result.metrics.get("excluded_metric_keys", ())
        for result in results
    )


def _penalty_value(result: TuningCandidateResult, key: str) -> float:
    components = result.metrics.get("objective_components", {})
    if not isinstance(components, Mapping):
        return 0.0
    penalties = components.get("penalties", {})
    if not isinstance(penalties, Mapping):
        return 0.0
    return _ratio(penalties.get(key, 0.0), default=0.0)


def _leakage_warnings(results: Sequence[TuningCandidateResult]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for result in results:
        excluded = list(result.metrics.get("excluded_metric_keys", ()))
        if excluded:
            warnings.append(
                {
                    "candidate_id": result.candidate.candidate_id,
                    "code": "FUTURE_INPUT_EXCLUDED",
                    "excluded_metric_keys": excluded,
                }
            )
    return warnings


def _available_output_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [_available_output_row(row) for row in rows]


def _available_output_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": row.get("snapshot_id"),
        "status": row.get("status"),
        "diagnostic_only": row.get("diagnostic_only"),
        "component_count": row.get("component_count"),
        "component_scores": dict(row.get("component_scores") or {}),
        "component_confidences": dict(row.get("component_confidences") or {}),
        "dominant_scenario": row.get("dominant_scenario"),
        "scenario_probabilities": dict(row.get("scenario_probabilities") or {}),
        "macro_overlay": dict(row.get("macro_overlay") or {}),
    }


def _objective_reason_codes(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    leakage_audit_codes = {"FUTURE_INPUT_EXCLUDED"}
    return {
        code
        for row in rows
        for code in row.get("reason_codes", ())
        if code not in leakage_audit_codes
    }


def _required_ratio(parameters: Mapping[str, Any], key: str) -> float:
    if key not in parameters:
        raise ValueError(f"{key} is required for diagnostic tuning execution")
    value = float(parameters[key])
    if not 0.0 < value < 1.0:
        raise ValueError(f"{key} must be between 0 and 1")
    return value


def _ratio(value: Any, *, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, result))


def _one_cycle_only_penalty(parameters: Mapping[str, Any]) -> float:
    active_cycle_count = parameters.get("diagnostic_active_cycle_count")
    if active_cycle_count is None:
        return 0.0
    try:
        return 0.5 if int(active_cycle_count) < 2 else 0.0
    except (TypeError, ValueError):
        return 0.5


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
