from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from api.domain.decision_state import LayerOutputEnvelope
from api.score_pipeline.orchestrator import DecisionOrchestrator
from api.score_pipeline.orchestrator_contracts import DecisionLayerId, DecisionRequest, DecisionRunMode


def test_fake_layer_runners_execute_in_defined_order():
    calls: list[str] = []
    request = _request()
    orchestrator = DecisionOrchestrator(
        [
            _FakeRunner(DecisionLayerId.MACRO, calls),
            _FakeRunner(DecisionLayerId.DATA, calls),
            _FakeRunner(DecisionLayerId.SCORE, calls),
        ]
    )

    result = orchestrator.run(request)

    assert calls == [DecisionLayerId.DATA, DecisionLayerId.SCORE, DecisionLayerId.MACRO]
    assert [output.layer for output in result.state_snapshot.layer_outputs] == calls


def test_lower_layer_warning_is_collected_as_feedback_signal():
    request = _request()
    orchestrator = DecisionOrchestrator(
        [_FakeRunner(DecisionLayerId.DATA, [], warnings=("LOW_DATA_QUALITY_REVIEW_REQUIRED",))]
    )

    result = orchestrator.run(request)

    assert len(result.state_snapshot.feedback_signals) == 1
    assert result.state_snapshot.feedback_signals[0].recommended_action == "REVIEW_REQUIRED"


def test_result_contains_state_snapshot_and_execution_remains_disabled():
    result = DecisionOrchestrator([_FakeRunner(DecisionLayerId.AUDIT, [])]).run(_request())

    assert result.state_snapshot.snapshot_id == "run-001-state"
    assert result.review_only is True
    assert result.execution_allowed is False


def test_controlled_refinement_plan_is_metadata_only_and_does_not_rerun_layers():
    calls: list[str] = []
    runner = _FakeRunner(DecisionLayerId.DATA, calls, warnings=("LOW_DATA_QUALITY_REVIEW_REQUIRED",))

    result = DecisionOrchestrator([runner]).run(_request())

    plan = result.state_snapshot.audit_metadata["controlled_refinement_plan"]
    assert calls == [DecisionLayerId.DATA]
    assert plan["metadata_only"] is True
    assert plan["layers_to_revisit"] == (DecisionLayerId.MACRO, DecisionLayerId.ALLOCATION)


def test_decision_orchestrator_module_stays_pure():
    path = Path("api/score_pipeline/orchestrator.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"fastapi", "starlette", "sqlite3", "api.db", "api.features", "api.strategy"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)


def _request() -> DecisionRequest:
    return DecisionRequest(
        run_id="run-001",
        as_of_date=date(2024, 3, 10),
        mode=DecisionRunMode.REVIEW_ONLY,
        raw_inputs={"source": "fixture"},
        portfolio_state={},
        account_state={},
        parameter_version="params-v1",
    )


@dataclass
class _FakeRunner:
    layer_id: str
    calls: list[str]
    warnings: tuple[str, ...] = ()

    def run(self, request: DecisionRequest) -> LayerOutputEnvelope:
        self.calls.append(self.layer_id)
        return LayerOutputEnvelope(
            layer=self.layer_id,
            output_type="FakeLayerOutput",
            as_of_date=request.as_of_date,
            payload={"run_id": request.run_id},
            warnings=self.warnings,
        )
