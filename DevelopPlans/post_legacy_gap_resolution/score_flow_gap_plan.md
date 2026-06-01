# Score Flow Gap Plan

Status: planning only. No strategy behavior is changed by this document.

Canonical rule source: `MASTER_DEVELOPMENT_GUIDE.md`.

## Current Evidence

- `api/strategy/macro_engine.py` produces a bounded integer macro score and a
  discrete regime label.
- `api/strategy/macro_distribution.py` can translate the legacy macro decision
  into a simple distribution, but it is not the allocation input used by the
  current `TripleAAllocator` path.
- `api/strategy/triplea_allocator.py` still adjusts bucket targets with fixed
  regime-based shifts in `_macro_adjusted_profile`.
- `api/score_pipeline/engines.py` contains score-flow-oriented macro
  distribution, sector score, risk budget, allocation range, and rebalancing
  engine foundations.
- `DevelopPlans/STATUS.md` records that legacy/current engines for macro
  regime, sector tilt, risk budget, allocation, rebalancing, and order
  candidates remain partial relative to the root guide.

## Gap Summary

| gap_id | current state | guide-aligned target | risk | required owner confirmation |
|---|---|---|---|---|
| `SFG-001` | Macro decision uses threshold-like labels (`risk_on`, `neutral`, `cautious`, `risk_off`) | Macro state should flow as a continuous distribution input | Behavior change can alter risk posture across all backtests | `requires_owner_confirmation` |
| `SFG-002` | Allocation profile uses fixed bucket shifts by regime label | Bucket and asset adjustments should be score/intensity based | New formulas or defaults would be investment rules | `requires_owner_confirmation` |
| `SFG-003` | Score pipeline allocation ranges are not the main allocator output contract | Existing `AllocationDecision` must remain API/backtest-compatible while target ranges are introduced | Response shape or persistence can break if changed abruptly | `requires_owner_confirmation` |
| `SFG-004` | Rebalancing/order-candidate foundations exist but are not fully wired to score-flow intensity | Rebalancing intensity and review-only candidate generation should consume score-flow outputs after hard constraints | Could accidentally create execution-like behavior | `requires_owner_confirmation` |
| `SFG-005` | Backtests cover current allocator behavior, not a score-flow migration comparison | Walk-forward/backtest comparison should prove behavior before activation | Return-only optimization or overfit parameter selection risk | `requires_owner_confirmation` |

## Future Task Candidates

### `SFG-TASK-001` Macro Distribution Adapter

- Objective: expose macro distribution as an allocation input without replacing
  the current allocator behavior.
- Allowed change shape: adapter/contract and tests only.
- Required tests:
  - macro fixture to distribution output;
  - deterministic previous-score change handling;
  - conservative fallback when macro indicators are missing.
- Stop conditions:
  - distribution weights or confidence defaults require new business rules;
  - the task would change current allocation decisions.
- Approval: `requires_owner_confirmation` before activating the adapter in
  production allocation.

### `SFG-TASK-002` Fixed Bucket Shift Replacement Plan

- Objective: define how fixed shifts could become score/intensity-based
  adjustments.
- Allowed change shape: design spec and failing characterization tests only.
- Required tests:
  - current fixed-shift behavior characterization;
  - proposed score/intensity inputs documented with expected conservative
    fallback;
  - no live execution or order mutation.
- Stop conditions:
  - shift amounts, score formula, or parameter defaults are not explicitly
    approved;
  - hard constraints would become score penalties.
- Approval: `requires_owner_confirmation` before any allocation behavior
  changes.

### `SFG-TASK-003` Allocation Target Range Compatibility

- Objective: map score-pipeline allocation target ranges into the existing
  `AllocationDecision` shape without changing public API fields.
- Allowed change shape: compatibility adapter and tests.
- Required tests:
  - score-pipeline range output to `AllocationDecision`;
  - API/backtest response compatibility;
  - hard constraint output blocks risk increases before allocation.
- Stop conditions:
  - public response shape must change;
  - account constraints cannot be represented as hard constraints first.
- Approval: `requires_owner_confirmation` before route/backtest default wiring.

### `SFG-TASK-004` Rebalancing Intensity And Review-Only Candidate Flow

- Objective: connect rebalancing intensity to review-only candidate generation
  without execution.
- Allowed change shape: review-only output contract and tests.
- Required tests:
  - score-flow input to rebalancing decision;
  - `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY` fallback on
    missing data;
  - explicit absence of broker/KIS/order submission calls.
- Stop conditions:
  - the task needs live account state, order permission, broker mutation, or
    automatic execution;
  - the task would create real order candidates outside a review-only scope.
- Approval: `requires_owner_confirmation` before enabling in user-facing flows.

### `SFG-TASK-005` Walk-Forward And Backtest Validation Gate

- Objective: compare current behavior and proposed score-flow behavior before
  any activation.
- Allowed change shape: deterministic backtest/walk-forward validation suite.
- Required tests:
  - fixture ingestion through score-flow decision output;
  - backtest before execution;
  - no future-data leakage;
  - no parameter selection by highest historical return alone.
- Stop conditions:
  - validation requires live execution or real account mutation;
  - benchmark period, objective function, or acceptance metric is unclear.
- Approval: `requires_owner_confirmation` before promoting any parameter or
  changing defaults.

## Non-Goals

- No macro score formula changes.
- No bucket shift amount changes.
- No sector score, risk budget, allocation, rebalancing, order-candidate, broker,
  KIS, or execution behavior changes.
- No automatic parameter promotion.
- No live order execution or real-account mutation.

## Conservative Fallback

Until the future tasks above are approved and tested, the current behavior
remains unchanged. Ambiguous inputs should remain `NO_ACTION`, `HOLD`,
`REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY` rather than inventing missing
investment rules.
