from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from api.domain.decision_feedback import (
    FeedbackSeverity,
    FeedbackSignal,
    FeedbackSourceLayer,
    FeedbackTargetLayer,
    FeedbackTiming,
    block_signal,
)
from api.domain.decision_state import (
    DecisionStateContractError,
    DecisionStateSnapshot,
    LayerOutputEnvelope,
)


def test_layer_output_envelope_preserves_payload_and_traceability():
    envelope = LayerOutputEnvelope(
        layer="MACRO",
        output_type="MacroRegimeDistribution",
        as_of_date=date(2024, 3, 10),
        payload={"dominant_regime": "neutral"},
        reason_codes=("MACRO_DISTRIBUTION",),
        warnings=("REVIEW_ONLY",),
        parameter_version="fixture-params",
        model_version="fixture-model",
    )

    assert envelope.payload["dominant_regime"] == "neutral"
    assert envelope.reason_codes == ("MACRO_DISTRIBUTION",)


def test_feedback_filtering_by_target_layer():
    snapshot = _snapshot(
        feedback_signals=(
            _signal("macro-feedback", (FeedbackTargetLayer.MACRO,)),
            _signal("risk-feedback", (FeedbackTargetLayer.RISK_BUDGET,)),
        )
    )

    assert [signal.signal_id for signal in snapshot.feedback_for_layer(FeedbackTargetLayer.MACRO)] == ["macro-feedback"]
    assert snapshot.feedback_for_layer(FeedbackTargetLayer.ALLOCATION) == ()


def test_outputs_filtering_by_layer():
    snapshot = _snapshot(
        layer_outputs=(
            LayerOutputEnvelope("MACRO", "Distribution", date(2024, 3, 10), {"value": 1}),
            LayerOutputEnvelope("RISK_BUDGET", "Risk", date(2024, 3, 10), {"value": 2}),
        )
    )

    assert [output.output_type for output in snapshot.outputs_for_layer("MACRO")] == ["Distribution"]


def test_blocking_feedback_detection():
    snapshot = _snapshot(
        feedback_signals=(
            block_signal(
                signal_id="block-risk",
                source_layer=FeedbackSourceLayer.ACCOUNT_CONSTRAINT,
                target_layers=(FeedbackTargetLayer.ALLOCATION,),
                as_of_date=date(2024, 3, 10),
                reason_codes=("ACCOUNT_BLOCK",),
                message="Account constraint blocks risk increase.",
            ),
        )
    )

    assert snapshot.has_blocking_feedback()


def test_next_run_input_contains_minimal_feedback_summary():
    snapshot = _snapshot(
        feedback_signals=(_signal("review", (FeedbackTargetLayer.MACRO,)),),
        next_run_inputs={"macro_review_state": "REVIEW_REQUIRED"},
    )

    payload = snapshot.to_next_run_input()

    assert payload["as_of_date"] == "2024-03-10"
    assert payload["previous_run_id"] == "run-001"
    assert payload["feedback_signals"][0]["signal_id"] == "review"
    assert payload["next_run_inputs"] == {"macro_review_state": "REVIEW_REQUIRED"}


@pytest.mark.parametrize("forbidden_key", ["submit_order", "place_order", "execution_allowed", "INCREASE_RISK"])
def test_forbidden_broker_or_execution_keys_fail(forbidden_key):
    with pytest.raises(DecisionStateContractError):
        _snapshot(next_run_inputs={forbidden_key: True})


def test_layer_output_payload_forbidden_execution_key_fails():
    with pytest.raises(DecisionStateContractError):
        LayerOutputEnvelope(
            layer="ORDER_CANDIDATE",
            output_type="Candidate",
            as_of_date=date(2024, 3, 10),
            payload={"nested": {"SUBMIT_ORDER": True}},
        )


def test_snapshot_requires_immutable_tuples():
    with pytest.raises(DecisionStateContractError):
        DecisionStateSnapshot(
            snapshot_id="snapshot-001",
            as_of_date=date(2024, 3, 10),
            run_id="run-001",
            layer_outputs=[],
            feedback_signals=(),
        )


def test_decision_state_domain_module_stays_pure():
    path = Path("api/domain/decision_state.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"fastapi", "starlette", "sqlite3", "api.db", "api.features"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)


def _snapshot(
    *,
    layer_outputs: tuple[LayerOutputEnvelope, ...] = (),
    feedback_signals: tuple[FeedbackSignal, ...] = (),
    next_run_inputs: dict[str, object] | None = None,
) -> DecisionStateSnapshot:
    return DecisionStateSnapshot(
        snapshot_id="snapshot-001",
        as_of_date=date(2024, 3, 10),
        run_id="run-001",
        layer_outputs=layer_outputs,
        feedback_signals=feedback_signals,
        next_run_inputs=next_run_inputs or {},
    )


def _signal(signal_id: str, target_layers: tuple[str, ...]) -> FeedbackSignal:
    return FeedbackSignal(
        signal_id=signal_id,
        source_layer=FeedbackSourceLayer.DATA_QUALITY,
        target_layers=target_layers,
        severity=FeedbackSeverity.REVIEW_REQUIRED,
        timing=FeedbackTiming.SAME_RUN_REFINEMENT,
        as_of_date=date(2024, 3, 10),
        reason_codes=("REVIEW_REQUIRED",),
        message="Review required.",
        recommended_action="REVIEW_REQUIRED",
    )
