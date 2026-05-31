# CapEx Cycle Runbook

## Scope

This runbook covers the read-only AI/Bio CapEx cycle scoring slice:

- AI CapEx cycle feature output.
- Bio/Pharma CapEx bottleneck score output.
- CapEx scenario distribution output.
- CapEx valuation output.
- Fixture-based PIT backtest smoke and leakage checks.
- Read-only FastAPI endpoints under `/api/capex-cycle/*`.

This slice does not submit broker orders, create executable order payloads, change live account state, or promote parameters automatically.

## Test Commands

Run the focused verification suite with:

```bash
.venv/bin/python -m pytest tests/score_pipeline -q
.venv/bin/python -m pytest tests/data/adapters -q
.venv/bin/python -m pytest tests/features/capex_cycle -q
.venv/bin/python -m pytest tests/backtest/test_capex_cycle_walk_forward_smoke.py -q
.venv/bin/python -m pytest tests/backtest/test_capex_cycle_future_data_leakage.py -q
.venv/bin/python -m pytest tests/architecture/test_capex_import_boundaries.py -q
git status --short
```

The backtest smoke test is deterministic and uses local fixture PIT data only.

## Data Quality Fallbacks

The CapEx slice treats uncertain inputs conservatively:

- Missing required data returns neutral or unavailable read-only output with `REVIEW_REQUIRED` style reason/warning metadata.
- Future `available_at` rows are excluded by fixture adapters and rejected by snapshot/plugin guards when encountered.
- Stale or low-quality data lowers confidence and emits warnings.
- Valuation without required inputs keeps fair value fields as `None`; it does not infer a cheap/expensive action.

Allowed fallback states remain `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, and `RISK_REDUCE_ONLY`. These are review states, not execution instructions.

## Bio CapEx Bottleneck Interpretation

Bio/Pharma CapEx Bottleneck output is a factor-style bottleneck score for read-only analysis. It is not:

- a buy/sell signal;
- an account-specific target weight;
- a core/satellite classification;
- an executable rebalance instruction.

Clinical-event or single-pipeline-sensitive assets must remain observation-only unless a later explicit task defines separate rules.

## Shadow Mode Workflow

Use the CapEx endpoints and tests in shadow mode:

1. Run the focused test suite.
2. Review `reason_codes`, `warnings`, `confidence`, `data_quality`, `parameter_version`, and `model_version`.
3. Compare current outputs against prior snapshots or reports.
4. Mark uncertain cases for manual review instead of interpreting them as trade instructions.
5. Keep any live execution, broker/KIS calls, and account-specific actions disabled.

## Rollback Plan

Rollback should prefer data/config changes before code changes:

1. Roll back parameter/config versions if an approved parameter set causes unexpected read-only output.
2. Disable or ignore the read-only CapEx API/report slice in operations if review quality is insufficient.
3. Revert code commits only if contracts, imports, or tests reveal a structural issue.
4. Do not add live execution as part of rollback.

## Verification Notes

Last focused verification: 2026-05-31.

- `tests/score_pipeline -q`: 44 passed.
- `tests/data/adapters -q`: 12 passed.
- `tests/features/capex_cycle -q`: 33 passed.
- `tests/backtest/test_capex_cycle_walk_forward_smoke.py -q`: 1 passed.
- `tests/backtest/test_capex_cycle_future_data_leakage.py -q`: 4 passed.
- `tests/architecture/test_capex_import_boundaries.py -q`: 3 passed.

`git status --short` may show pre-existing local changes outside this runbook; do not stage broker, account, order, execution, secret, runtime DB, cache, or web build artifacts as part of CapEx runbook updates.
