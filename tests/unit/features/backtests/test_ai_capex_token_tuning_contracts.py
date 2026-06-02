from __future__ import annotations

import pytest

from api.features.backtests.ai_capex_token_tuning_contracts import (
    AICapexTokenTuningContractError,
    TuningCandidate,
    TuningCandidateResult,
    TuningExecutionValidationResult,
    deterministic_hash,
)


def test_candidate_parameter_order_does_not_change_hash():
    first = TuningCandidate.from_parameters(
        candidate_id="candidate_a",
        parameters={"alpha": 0.3, "nested": {"beta": 0.7, "gamma": 1}},
        parameter_version="test_v1",
    )
    second = TuningCandidate.from_parameters(
        candidate_id="candidate_b",
        parameters={"nested": {"gamma": 1, "beta": 0.7}, "alpha": 0.3},
        parameter_version="test_v1",
    )

    assert first.parameter_hash == second.parameter_hash


def test_different_parameters_change_hash():
    base = deterministic_hash({"alpha": 0.3, "beta": 0.7})
    changed = deterministic_hash({"alpha": 0.4, "beta": 0.7})

    assert base != changed


def test_candidate_count_below_two_falls_to_noop_status():
    candidate = _candidate("candidate_a", 0.3)
    result = TuningCandidateResult.from_payloads(
        candidate=candidate,
        output_payload={"score": 0.5},
        metrics={"objective_score": 0.1},
        objective_score=0.1,
    )

    validation = TuningExecutionValidationResult.from_candidate_results(
        candidates=(result,),
        selected_candidate_id=None,
        memory_cycle_coverage={"distinct_cycle_count": 2, "cycle_ids": ["cycle_a", "cycle_b"]},
        leakage_check_passed=True,
        historical_cycle_passed=True,
    )

    assert validation.status == "FAIL_NOOP_TUNING"
    assert validation.no_op_tuning_detected is True


def test_candidate_requires_diagnostic_only_true():
    with pytest.raises(AICapexTokenTuningContractError):
        TuningCandidate.from_parameters(
            candidate_id="candidate_live",
            parameters={"alpha": 0.3},
            parameter_version="test_v1",
            diagnostic_only=False,
        )


def test_validation_requires_diagnostic_only_and_not_production_ready():
    candidate_a = _candidate("candidate_a", 0.3)
    candidate_b = _candidate("candidate_b", 0.4)
    result_a = TuningCandidateResult.from_payloads(
        candidate=candidate_a,
        output_payload={"score": 0.5},
        metrics={"objective_score": 0.1},
        objective_score=0.1,
    )
    result_b = TuningCandidateResult.from_payloads(
        candidate=candidate_b,
        output_payload={"score": 0.6},
        metrics={"objective_score": 0.2},
        objective_score=0.2,
    )

    with pytest.raises(AICapexTokenTuningContractError):
        TuningExecutionValidationResult.from_candidate_results(
            candidates=(result_a, result_b),
            selected_candidate_id="candidate_b",
            memory_cycle_coverage={"distinct_cycle_count": 2, "cycle_ids": ["cycle_a", "cycle_b"]},
            leakage_check_passed=True,
            historical_cycle_passed=True,
            diagnostic_only=False,
        )
    with pytest.raises(AICapexTokenTuningContractError):
        TuningExecutionValidationResult.from_candidate_results(
            candidates=(result_a, result_b),
            selected_candidate_id="candidate_b",
            memory_cycle_coverage={"distinct_cycle_count": 2, "cycle_ids": ["cycle_a", "cycle_b"]},
            leakage_check_passed=True,
            historical_cycle_passed=True,
            production_ready=True,
        )


def test_validation_counts_unique_signatures():
    candidate_a = _candidate("candidate_a", 0.3)
    candidate_b = _candidate("candidate_b", 0.4)
    result_a = TuningCandidateResult.from_payloads(
        candidate=candidate_a,
        output_payload={"score": 0.5, "reason_codes": ["A"]},
        metrics={"objective_score": 0.1},
        objective_score=0.1,
    )
    result_b = TuningCandidateResult.from_payloads(
        candidate=candidate_b,
        output_payload={"score": 0.6, "reason_codes": ["B"]},
        metrics={"objective_score": 0.2},
        objective_score=0.2,
    )

    validation = TuningExecutionValidationResult.from_candidate_results(
        candidates=(result_a, result_b),
        selected_candidate_id="candidate_b",
        memory_cycle_coverage={"distinct_cycle_count": 2, "cycle_ids": ["cycle_a", "cycle_b"]},
        leakage_check_passed=True,
        historical_cycle_passed=True,
    )

    assert validation.status == "PASS_HISTORICAL_DIAGNOSTIC"
    assert validation.unique_parameter_hash_count == 2
    assert validation.unique_output_signature_count == 2
    assert validation.unique_metric_signature_count == 2
    assert validation.to_dict()["candidate_count"] == 2


def _candidate(candidate_id: str, alpha: float) -> TuningCandidate:
    return TuningCandidate.from_parameters(
        candidate_id=candidate_id,
        parameters={"alpha": alpha},
        parameter_version="test_v1",
    )
