# Layered Score Flow Feedback Baseline Inventory

Task: `001_inspect_layered_feedback_current_baseline`

This inventory records the current repository baseline before adding layered
score-flow feedback contracts. It is inspection-only and does not approve any
activation of new allocation, rebalancing, or order behavior.

## Evidence Read

- `DevelopPlans/STATUS.md`
- `DevelopPlans/post_legacy_gap_resolution/score_flow_gap_plan.md`
- `DevelopPlans/post_legacy_gap_resolution/current_gap_inventory.md`
- `api/strategy/macro_engine.py`
- `api/strategy/macro_distribution.py`
- `api/strategy/triplea_allocator.py`
- `api/score_pipeline/contracts.py`
- `api/score_pipeline/engines.py`
- `api/domain/strategy_inputs.py`
- `api/strategy/data_ports.py`
- `tests/integration/pipeline/test_strategy_engine_decoupled_input_to_output.py`

## Baseline Map

| area | current file | current behavior | target contract | allowed next change | stop condition |
|---|---|---|---|---|---|
| macro snapshot input | `api/domain/strategy_inputs.py`, `api/strategy/data_ports.py` | `MacroSnapshotInput` carries as-of indicators and `MacroSnapshotReader` supplies it by date. | Keep as read-only input contract for score-flow adapters. | Add adapter-facing contract references only. | Any change requiring new macro source ownership, live data dependency, or numeric default. |
| macro decision output | `api/strategy/macro_engine.py` | `MacroEngine` returns `MacroRegimeDecision` with bounded integer score and discrete `regime`. | Treat as legacy macro decision input for non-activating adapters. | Add mapping contracts without changing `_regime_from_score` or active reasons. | Any change to macro thresholds, score formula, or active regime labels. |
| macro distribution adapter | `api/strategy/macro_distribution.py` | Converts `MacroRegimeDecision` to a simple distribution with fixed confidence/data quality values; not wired into allocator. | Adapter contract that preserves legacy input while producing reviewable distribution metadata. | Add conservative contract/adapter tests only. | Owner confirmation needed for new distribution weights, confidence defaults, or active use. |
| score pipeline macro distribution | `api/score_pipeline/contracts.py`, `api/score_pipeline/engines.py` | `MacroRegimeDistribution` and `MacroRegimeEngine` exist in score-pipeline foundation with explanation-only dominant regime. | Use as contract boundary for future layered score flow. | Add bridge/skeleton contracts that do not affect active allocator behavior. | Any activation in allocation/rebalancing/order candidate path. |
| allocation decision compatibility | `api/strategy/triplea_allocator.py`, `api/strategy/types.py` | `TripleAAllocator.allocate` returns legacy `AllocationDecision`; macro label drives `_macro_adjusted_profile` bucket shifts. | Preserve existing public allocation output while future score-flow output remains separate/non-activating. | Add compatibility snapshot contracts only. | Any change to bucket shifts, final weights, sector tilt, risk budget, or public allocation behavior. |
| feedback signal need | no dedicated file yet | No explicit feedback signal contract records score-flow distribution change, data quality, and review-only action together. | `FeedbackSignal` style domain contract with conservative status and traceability. | Add contract in `api/domain/` or `api/score_pipeline/` with tests. | Any signal that directly triggers buy/sell/risk increase or changes active strategy. |
| decision state snapshot need | no dedicated file yet | Current integration test validates raw input to allocation output but does not expose a stable decision state snapshot contract. | Snapshot contract for as-of date, inputs, distributions, warnings, and conservative output state. | Add immutable contract and serialization tests. | Public API shape changes or executable order/execution fields. |
| orchestrator need | no active layered orchestrator | Existing score-pipeline engines are independent; active strategy allocator is separate. | Non-activating orchestrator skeleton that returns contracts for audit/test only. | Add skeleton that is not wired into app routes or allocator. | Any wiring into production allocation/rebalancing/order behavior. |
| controlled refinement pass need | `DevelopPlans/post_legacy_gap_resolution/score_flow_gap_plan.md` | Refinement is planned but requires owner confirmation before behavior activation. | Contract for feedback collection and future controlled refinement handoff. | Document/test non-mutating feedback collection only. | Automatic parameter promotion, score formula change, or owner-unapproved tuning. |
| no-execution boundary | `api/score_pipeline/contracts.py`, architecture tests | Score-pipeline `OrderCandidate` requires `execution_allowed` false; simplified architecture tests guard live execution. | Keep feedback layer review-only and execution-free. | Add guardrails proving no live/broker/order execution dependency. | Any live broker/KIS/order submission, real account mutation, or automatic execution path. |

## Conclusions

- This inventory is not behavior activation approval.
- This task pack may add adapter, contract, skeleton, and test artifacts only.
- Active allocation, rebalancing, order candidate, broker, KIS, or execution behavior changes require separate owner confirmation.
- Missing or uncertain business rules must remain `REVIEW_REQUIRED`, `NO_ACTION`, `HOLD`, or `RISK_REDUCE_ONLY`.
