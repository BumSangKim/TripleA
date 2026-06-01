from __future__ import annotations

from dataclasses import asdict
from typing import Sequence

from api.domain.decision_state import DecisionStateSnapshot, LayerOutputEnvelope
from api.score_pipeline.contracts import DecisionWarning
from api.score_pipeline.feedback import FeedbackCollector
from api.score_pipeline.orchestrator_contracts import (
    ControlledRefinementPlan,
    DecisionLayerId,
    DecisionRequest,
    DecisionResult,
    LayerRunner,
)


LAYER_ORDER = (
    DecisionLayerId.DATA,
    DecisionLayerId.FEATURE,
    DecisionLayerId.SCORE,
    DecisionLayerId.MACRO,
    DecisionLayerId.SECTOR_ASSET,
    DecisionLayerId.RISK_BUDGET,
    DecisionLayerId.ALLOCATION,
    DecisionLayerId.REBALANCING,
    DecisionLayerId.ACCOUNT_CONSTRAINT,
    DecisionLayerId.ORDER_CANDIDATE,
    DecisionLayerId.AUDIT,
)


class DecisionOrchestrator:
    """Non-activating score-flow runner skeleton.

    The skeleton collects layer outputs and feedback into a state snapshot. It
    does not wire into app routes, allocators, backtests, or execution paths.
    """

    def __init__(
        self,
        layer_runners: Sequence[LayerRunner],
        feedback_collector: FeedbackCollector | None = None,
    ) -> None:
        self.layer_runners = tuple(layer_runners)
        self.feedback_collector = feedback_collector or FeedbackCollector()

    def run(self, request: DecisionRequest) -> DecisionResult:
        layer_outputs = tuple(runner.run(request) for runner in self._ordered_runners())
        feedback_inputs = [*layer_outputs, *_warnings_from_outputs(layer_outputs)]
        feedback_signals = self.feedback_collector.collect(*feedback_inputs, as_of_date=request.as_of_date)
        refinement_plan = ControlledRefinementPlan.from_feedback_signals(feedback_signals)
        snapshot = DecisionStateSnapshot(
            snapshot_id=f"{request.run_id}-state",
            as_of_date=request.as_of_date,
            run_id=request.run_id,
            layer_outputs=layer_outputs,
            feedback_signals=feedback_signals,
            next_run_inputs={},
            audit_metadata={
                "controlled_refinement_plan": {
                    "layers_to_revisit": refinement_plan.layers_to_revisit,
                    "reason_codes": refinement_plan.reason_codes,
                    "metadata_only": True,
                }
            },
        )
        return DecisionResult(
            run_id=request.run_id,
            as_of_date=request.as_of_date,
            mode=request.mode,
            state_snapshot=snapshot,
        )

    def _ordered_runners(self) -> tuple[LayerRunner, ...]:
        order = {layer: index for index, layer in enumerate(LAYER_ORDER)}
        return tuple(sorted(self.layer_runners, key=lambda runner: order.get(runner.layer_id, len(order))))


def _warnings_from_outputs(outputs: tuple[LayerOutputEnvelope, ...]) -> tuple[DecisionWarning, ...]:
    warnings: list[DecisionWarning] = []
    for output in outputs:
        for warning in output.warnings:
            warnings.append(
                DecisionWarning(
                    code=warning,
                    severity="WARNING",
                    source=output.layer,
                    message=warning,
                )
            )
    return tuple(warnings)


def state_snapshot_dict(result: DecisionResult) -> dict:
    return asdict(result.state_snapshot)
