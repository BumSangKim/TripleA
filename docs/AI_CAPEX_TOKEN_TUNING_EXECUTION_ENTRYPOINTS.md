# AI Capex-Token Tuning Execution Entrypoints

## Scope

This document records the safe entrypoints for verifying that the AI
Capex-Token tuning loop is not a no-op. It is not a production tuning approval
document.

## Existing Entrypoints

- `api/features/backtests/ai_capex_token_diagnostic.py`
  - Builds the current read-only diagnostic payload used by backtest/UI
    diagnostics.
  - Keeps `diagnosticOnly: true` and `productionReady: false`.
- `api/strategy/ai_capex_token_component.py`
  - Builds diagnostic-only sector component scores from fixture/snapshot input.
  - Does not apply results to the sector engine.
  - Keeps `applied_to_sector_engine=False`.
- `api/score_pipeline/backtest.py`
  - Provides local simulation contracts and result metrics.
  - Does not require broker, account, or execution paths.
- `api/score_pipeline/parameters.py`
  - Provides versioned parameter lookup and conservative fallback behavior.
- `tests/fixtures/ai_capex_token/`
  - Contains current deterministic AI Capex-Token fixtures.
- `reports/backtest/ai_capex_token_adaptive/`
  - Contains existing diagnostic/shadow reports from the adaptive tuning
    checkpoint.

## Forbidden Paths

The tuning execution verification package must not modify or call live
execution paths:

- `api/brokers/**`
- `api/execution/**`
- `api/orders/**`
- `api/account/**`
- broker/KIS credential or order submission paths
- `config/scoring/ai_capex_token.yaml` production enablement or approval fields

## Safe Harness Location

Use a new diagnostic-only harness under:

```text
api/score_pipeline/plugins/ai_capex_token_tuning_execution.py
```

This keeps the verification loop independent from production strategy and UI
wiring while still validating:

```text
candidate parameters
-> leakage-safe fixture snapshots
-> adaptive feature/scenario/sector diagnostic outputs
-> objective calculation
-> candidate ranking and rejection report
```

## Required Test Areas

- Contract/unit tests under `tests/unit/score_pipeline/`.
- Backtest/report tests under `tests/backtest/`.
- Existing AI Capex-Token fixtures under `tests/fixtures/ai_capex_token/`.
- Existing no-lookahead/leakage tests under `tests/backtest/`.
- Architecture guardrails under `tests/architecture/`.

## Tuning Execution Decision

Safe extension point: approved for diagnostic harness implementation only.

Production enablement: not allowed.

Order/execution/broker wiring: not allowed.

Historical tuning pass: only allowed if two explicit memory cycles are proven.
Otherwise the verification may pass synthetic smoke tests only and must report
`REVIEW_REQUIRED` for historical validation.
