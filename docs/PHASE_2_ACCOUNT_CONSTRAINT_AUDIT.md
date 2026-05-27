# Phase 2 Account Constraint Audit

## Existing Account-Related Files

- `api/models.py`: account summaries, account policies, snapshots, rebalancing results, order drafts, and backtest response models.
- `api/db.py`: `accounts`, `account_policies`, `account_snapshots`, `holdings`, `rebalance_results`, order tables, and backtest tables.
- `api/modes.py`: mode-level safety policy for mock, test, backtest, paper, and live.
- `api/providers.py`: provider routing and read-only KIS account sync for paper/live account snapshots.
- `api/services.py`: account policy reads, snapshot persistence, rebalancing suggestions, order draft creation, paper approval logging, and backtest persistence.
- `api/asset_universe_schema.py`: Phase 1 account eligibility metadata for assets.
- `config/asset_universe.yaml`: Phase 1 asset universe with account eligibility metadata.
- `config/investment_universe.yaml` and `config/backtest_assets.yaml`: legacy/current universe inputs for allocator and backtest.

## Existing Constraint Logic

- Mode policies block writes and execution in mock/test/backtest and keep live order execution disabled.
- `api/services.py::create_order_draft` generates paper order candidates from rebalancing deviations but does not yet apply a dedicated account constraint engine.
- `api/services.py::approve_order_draft` rejects live execution and records paper approval as `APPROVED_NOT_SENT`.
- `api/db.py::_seed_account_policies` stores account policy descriptions, but these are not machine-readable hard constraints.
- Phase 1 asset eligibility metadata marks unknown account eligibility conservatively, but it is not yet a reusable constraint engine.

## Reusable Components

- `api/asset_universe_schema.py::get_account_eligibility` can inform account/product eligibility adapters.
- Existing mode policy objects are useful execution-boundary context, but they should not be changed in Phase 2.
- Existing account snapshot and holding tables can provide future `AccountState` and `PositionState` inputs.
- Backtest engine inputs are deterministic and as-of-date based, which matches the Phase 2 requirement for pure constraint evaluation.

## Missing Components

- Canonical account constraint configuration with account types, roles, allowed asset classes, blocked flags, cash rules, and IRP risky asset limits.
- Explicit account constraint domain models.
- A deterministic rule engine that returns block/reduce/review/allow results with reason codes.
- Trade eligibility validation reusable by allocation, rebalancing, order candidates, and backtests.
- Conservative fallback helpers for unknown account, product, balance, position, and API states.
- Standard audit payload contract for reporting and future decision logs.

## Minimal Implementation Plan

1. Add `docs/ACCOUNT_CONSTRAINT_ENGINE_SPEC.md`.
2. Add `config/account_constraints.yaml` and a loader/validator.
3. Add `api/strategy/account_constraints/` with explicit models, rule engine, fallback helper, trade eligibility validator, and audit serializer.
4. Add focused tests under `tests/strategy/`.
5. Keep existing allocation, rebalancing, order draft, broker/KIS, execution, and backtest behavior unchanged.

## Test Plan

- Shell checks for required documentation sections.
- Config loader tests for valid config, missing fields, unknown account types, and IRP risky asset limits.
- Domain model tests for enum validation, conservative result serialization, and missing-field behavior.
- Rule engine tests for account/product eligibility, restricted flags, cash/order placeholders, IRP risky asset limits, and conservative fallbacks.
- Backtest compatibility tests for deterministic outputs and as-of audit payloads.
- Final full pytest run after all Phase 2 tasks.

## Explicit Non-Goals

- No live order execution.
- No automatic order execution.
- No broker API order submission.
- No change to existing allocation, rebalancing, order candidate, provider, KIS, or backtest behavior.
- No broad refactor of current dashboard services or API routes.
- No treating hard constraints as score penalties.
