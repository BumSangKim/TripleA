# Simplified Architecture Contract

This document freezes the simplification target for TripleA. It is a
task-specific contract for removing real-account and broker-linked behavior.
The canonical development guide remains `MASTER_DEVELOPMENT_GUIDE.md` at the
repository root.

## Scope

The simplified architecture is local, deterministic, and simulation-only. It
keeps enough domain logic to validate investment decisions through backtests and
code contracts, but it does not connect to a live brokerage account or submit
orders.

## Allowed Areas

- Deterministic or local data collection fixtures.
- Data validation and data quality metadata.
- Feature layer inputs and derived feature values.
- Continuous score layer contracts and pure score-flow logic.
- Macro, sector, risk, allocation, and rebalancing pure logic.
- Backtest engine and backtest fixtures.
- Reporting and audit outputs.
- Simulated account and account constraint models for backtest validation only.

## Removed Areas

- Broker adapters.
- KIS or other live brokerage API integration.
- Live account balance synchronization.
- Live or paper execution engines that imply broker-side order handling.
- Order candidate API/features and executable order drafts.
- Automatic order execution.
- Tests that require network access, credentials, real account state, external
  services, local secret files, or mutable live provider state.

## Preserved Domain Boundaries

Pure account and account constraint models are not live integration by
themselves. They remain valid when used to evaluate hard constraints in
deterministic tests, simulated portfolios, and backtests.

Hard constraints must remain hard constraints. They must not be weakened into
score penalties, downstream hints, or optional warnings.

## Supported Outputs

The simplified system may produce only local or simulation-safe outputs:

- `DecisionSnapshot`
- `RebalancePlan`
- `BacktestReport`
- `AuditLog`

These outputs may describe local decisions, reasons, constraints, warnings,
rebalance plans, and simulated results. They must not expose order candidates,
submit orders, mutate a real account, or trigger broker execution.

## Fallback Rules

When data, configuration, metadata, or account assumptions are incomplete, the
system must use conservative states such as:

- `NO_ACTION`
- `HOLD`
- `REVIEW_REQUIRED`
- `RISK_REDUCE_ONLY`

The simplified architecture must not default to `BUY`, `FORCE_REBALANCE`,
`AUTO_EXECUTE`, `LIVE_EXECUTE`, or any behavior that increases risk without an
explicit tested rule.

## Documentation Relationship

This directory is not a replacement for the root development guide. It exists
only to define the simplification contract and the supported test strategy for
this task batch. Do not recreate a parallel documentation tree or make
`docs/` the source of truth for development rules.
