# Layered Score Flow Feedback Target Architecture Contract

Task: `002_write_target_architecture_contract_current_tree`

This contract applies to the current repository tree. It does not recreate a
`docs/` source of truth and does not authorize active strategy behavior changes.

## 1. Architecture Decision

TripleA uses a contract-based downward score-flow pipeline, not a fully
independent module system.

The system may perform cyclical judgment through explicit feedback artifacts,
but it must not introduce cyclical dependencies. A lower layer may report its
state, quality, constraints, or outcome through a feedback contract. It must not
call an upper layer directly.

## 2. Layer Execution Rule

The target execution order is:

```text
Data
-> Feature
-> Score
-> Macro
-> Sector/Asset
-> Risk
-> Allocation
-> Rebalancing
-> Constraint
-> Order Candidate
-> Audit
```

This sequence is a dependency direction rule. It is not approval to replace
current allocation, rebalancing, or order candidate behavior.

## 3. Feedback Rule

Lower layers do not import or call upper layers. They may only emit explicit
feedback outputs:

- `FeedbackSignal`
- `ConstraintFeedback`
- `RiskFeedback`
- `OutcomeFeedback`
- `BacktestFeedback`
- `AuditFeedback`

The orchestrator is the only component allowed to promote feedback into either
same-run refinement input or next-run input. Feedback outputs are review and
traceability artifacts until owner approval activates any behavior change.

## 4. Controlled Refinement Pass

The target controlled pass is:

```text
preliminary output
-> feedback collection
-> finalization
```

Finalization remains skeleton/contract-only in this task pack. Any change that
would alter active score formulas, macro thresholds, bucket shifts, sector tilt,
allocation weights, rebalancing actions, order candidates, broker behavior, or
execution behavior is a stop condition requiring separate owner confirmation.

## 5. File Ownership Target

Target ownership for future tasks:

- `api/domain/decision_feedback.py`: pure feedback/domain contracts.
- `api/domain/decision_state.py`: decision state snapshot contract.
- `api/score_pipeline/feedback.py`: feedback collector contract.
- `api/score_pipeline/adapters/macro_distribution_adapter.py`: SFG-TASK-001 non-activating adapter.
- `api/score_pipeline/orchestrator_contracts.py`: orchestrator request/result contracts.
- `api/score_pipeline/orchestrator.py`: non-activating runner skeleton.

These files must stay independent unless a task explicitly requires a contract
import. Domain files must remain pure Python contracts.

## 6. Forbidden Dependencies

The following dependency directions are forbidden:

- `api/domain/**` importing FastAPI, `sqlite3`, `api.db`, or `api.features`.
- `api/strategy/**` importing the concrete score-pipeline orchestrator.
- Any lower layer directly importing or calling an upper layer implementation.
- Any new file adding broker, KIS, order execution mutation, live account
  mutation, or automatic execution behavior.

## 7. Testing Matrix

Required validation areas:

- Contract tests for pure feedback and decision state objects.
- Raw fixture -> macro reader -> macro distribution adapter -> feedback output
  -> decision state output.
- Architecture guardrails preventing forbidden imports and execution behavior.

Tests must validate traceability from input or fixture collection to final
output contract. Where behavior is not owner-approved, outputs must remain
non-activating and conservative.

## 8. Migration Gates

- `SFG-TASK-001`: adapter/contract only. No active behavior replacement.
- `SFG-TASK-002+`: behavior changes require owner confirmation before coding.

Allowed conservative states are `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, and
`RISK_REDUCE_ONLY`. Any owner-unapproved behavior that increases risk, promotes
parameters, or creates live execution intent is forbidden.
