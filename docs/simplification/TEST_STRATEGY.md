# Simplified Test Strategy

This document defines the supported test categories for the simplified TripleA
architecture. The test strategy follows `MASTER_DEVELOPMENT_GUIDE.md` and the
simplified architecture contract in `docs/simplification/SIMPLIFIED_ARCHITECTURE.md`.

## Supported Test Categories

- Backtest tests: deterministic simulations that validate portfolio state,
  historical data ordering, metrics, conservative fallback behavior, and
  reportable results. The current repository directory is `tests/backtest`.
- Unit and code contract tests: pure code tests for loaders, validators,
  domain models, score-flow contracts, account constraints, and reporting
  contracts. Simplification-specific code checks live in `tests/code`.
- Architecture and import-boundary tests: static or import-safe tests that
  prevent broker, KIS, live account, and live execution dependencies from
  returning to active code paths.
- Deterministic data-to-output integration tests: fixture-based tests that
  validate the observable flow from raw input through validation, feature or
  score behavior, allocation or rebalancing logic where available, and final
  simulation-safe output.

## Unsupported Test Categories

- Tests requiring real account credentials or local secret material.
- Tests requiring live broker, KIS, Telegram, Slack, or other external services.
- Tests requiring network access or mutable provider state.
- Browser or UI end-to-end tests that depend on external services or real
  account state.
- Tests that validate actual order submission or real-account mutation.
- Tests marked as `live_price`; this marker is unsupported in the simplified
  suite.

## Required Data-To-Output Shape

At least one deterministic supported test must validate this shape:

```text
fixture raw input
-> collection or loading
-> validation and quality metadata
-> feature or score-flow contract
-> macro / sector / risk / allocation / rebalancing behavior where available
-> backtest or decision/report output
```

If a downstream stage is not implemented, the test must assert an explicit
conservative fallback such as `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or
`RISK_REDUCE_ONLY`; it must not invent an investment decision.

## Traceability Requirements

Supported output tests should verify traceability fields when the relevant
contract supports them:

- `as_of_date`
- data snapshot or data quality reference
- `parameter_version`
- `model_version`
- reason codes or warnings
- explicit absence of live execution intent

## Current Validation Commands

Task-specific commands may narrow this list. The final simplification sweep
uses these supported commands:

```bash
git diff --check
pytest -q --collect-only
pytest tests/backtest -q
pytest tests/code -q
pytest tests/architecture -q
```

The broader deterministic suite can be run separately with:

```bash
pytest tests/unit tests/integration -q
pytest tests -q
```

If repository test directories are renamed during explicit tasks, this file
must be updated with the exact supported commands.
