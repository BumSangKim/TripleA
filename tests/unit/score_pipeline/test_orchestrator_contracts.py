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
)
from api.domain.decision_state import DecisionStateSnapshot
from api.score_pipeline.orchestrator_contracts import (
    ControlledRefinementPlan,
    DecisionLayerId,
    DecisionRequest,
    DecisionResult,
    DecisionRunMode,
    OrchestratorContractError,
)


def test_valid_decision_request_and_result_can_be_created():
    request = DecisionRequest(
        run_id="run-001",
        as_of_date=date(2024, 3, 10),
        mode=DecisionRunMode.REVIEW_ONLY,
        raw_inputs={"source": "fixture"},
        portfolio_state={"cash": 1000},
        account_state={"account_type": "SIMULATED"},
        parameter_version="params-v1",
    )
    snapshot = DecisionStateSnapshot(
        snapshot_id="snapshot-001",
        as_of_date=request.as_of_date,
        run_id=request.run_id,
        layer_outputs=(),
        feedback_signals=(),
    )
    result = DecisionResult(
        run_id=request.run_id,
        as_of_date=request.as_of_date,
        mode=request.mode,
        state_snapshot=snapshot,
    )

    assert result.review_only is True
    assert result.execution_allowed is False


def test_execution_allowed_true_fails():
    snapshot = DecisionStateSnapshot(
        snapshot_id="snapshot-001",
        as_of_date=date(2024, 3, 10),
        run_id="run-001",
        layer_outputs=(),
        feedback_signals=(),
    )

    with pytest.raises(OrchestratorContractError):
        DecisionResult(
            run_id="run-001",
            as_of_date=date(2024, 3, 10),
            mode=DecisionRunMode.DRY_RUN,
            state_snapshot=snapshot,
            execution_allowed=True,
        )


def test_unknown_mode_or_layer_fails():
    with pytest.raises(OrchestratorContractError):
        DecisionRequest(
            run_id="run-001",
            as_of_date=date(2024, 3, 10),
            mode="LIVE",
            raw_inputs={},
            portfolio_state={},
            account_state={},
            parameter_version="params-v1",
        )

    with pytest.raises(OrchestratorContractError):
        ControlledRefinementPlan(feedback_signals=(), layers_to_revisit=("LIVE_EXECUTION",))


def test_refinement_plan_preserves_feedback_target_layers():
    signal = FeedbackSignal(
        signal_id="feedback-001",
        source_layer=FeedbackSourceLayer.DATA_QUALITY,
        target_layers=(FeedbackTargetLayer.MACRO, FeedbackTargetLayer.ALLOCATION),
        severity=FeedbackSeverity.REVIEW_REQUIRED,
        timing=FeedbackTiming.SAME_RUN_REFINEMENT,
        as_of_date=date(2024, 3, 10),
        reason_codes=("LOW_DATA_QUALITY",),
        message="Review required.",
        recommended_action="REVIEW_REQUIRED",
    )

    plan = ControlledRefinementPlan.from_feedback_signals((signal,))

    assert plan.layers_to_revisit == (DecisionLayerId.MACRO, DecisionLayerId.ALLOCATION)
    assert plan.reason_codes == ("LOW_DATA_QUALITY",)


@pytest.mark.parametrize("forbidden_key", ["submit_order", "place_order", "INCREASE_RISK"])
def test_request_forbidden_order_or_broker_keys_fail(forbidden_key):
    with pytest.raises(OrchestratorContractError):
        DecisionRequest(
            run_id="run-001",
            as_of_date=date(2024, 3, 10),
            mode=DecisionRunMode.REVIEW_ONLY,
            raw_inputs={forbidden_key: True},
            portfolio_state={},
            account_state={},
            parameter_version="params-v1",
        )


def test_orchestrator_contract_module_stays_pure():
    path = Path("api/score_pipeline/orchestrator_contracts.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"fastapi", "starlette", "sqlite3", "api.db", "api.features", "api.strategy"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)
