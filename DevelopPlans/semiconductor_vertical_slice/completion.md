# Semiconductor Vertical Slice Completion

Status: complete for `SEM-001` through `SEM-020` and `SEM-999`.

The slice is fixture-only and diagnostic/shadow-only. It adds point-in-time
raw observations, read-only market/FX snapshots, traceable feature contracts,
unapproved score/tilt candidates, look-through exposure, review-only rebalance
plans, synthetic validation backtests, and an audit handoff. Production remains
disabled and allocation contribution remains `0.0`.

Validation completed:

- collect-only: 1527 collected
- architecture: 72 passed, 1 expected xfail
- code: 9 passed
- unit: 300 passed
- integration: 79 passed
- backtest: 65 passed
- full suite: 1526 passed, 1 expected xfail

Known limitations:

- all semiconductor evidence is deterministic fixture validation, not factual
  historical performance evidence;
- no real constituent or market-data provider is connected;
- candidate component weights and production validation thresholds remain
  unapproved;
- tax policy remains unavailable in the review-only rebalance candidate.

Next task: add a read-only, environment-gated market/FX snapshot adapter with
independent historical fixture reconciliation while preserving all shadow-only
and no-execution boundaries.
