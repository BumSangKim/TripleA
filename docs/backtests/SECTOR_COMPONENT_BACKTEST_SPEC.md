# Sector Component Backtest Spec

## Purpose And Scope

The sector component backtest is a diagnostic validation path for historical sector component inputs. It verifies whether component observations can be transformed into reproducible snapshots, attribution rows, metric summaries, sensitivity diagnostics, and regime/stress breakdowns.

Out of scope:

- account strategy changes;
- account constraints;
- order candidate generation;
- broker integration;
- live or automatic execution;
- automatic production promotion of parameters.

## Input Contract

The runner accepts a parsed `SectorComponentBacktestConfig`, sector component observations, historical return records, and optional macro regime records.

Component observations must carry:

- `sector_id`;
- `component_name`;
- `score`;
- `as_of_date`;
- `available_at`;
- `parameter_version`;
- `model_version`;
- `data_snapshot_id`;
- optional `source`, `confidence`, and `data_quality` or fixture `quality_score`.

Historical return records must carry `sector_id`, `as_of_date`, and `forward_return` or `period_return`. Macro regime records must carry `sector_id`, `as_of_date`, and `regime`.

## Point-In-Time Rules

Snapshots are built with `api.plugin_boundary.time_guard.filter_available_values`. A row is eligible only when `available_at` is no later than the decision timestamp. Rows with future `available_at` are excluded from earlier snapshots, which prevents future-data leakage.

The result preserves `parameter_version`, `model_version`, and `data_snapshot_id` so a fixed fixture can reproduce the same output.

## Attribution

`calculate_sector_component_attribution` multiplies component score by the configured component weight. The output remains an attribution diagnostic:

- `score`;
- `weight`;
- `weighted_contribution`;
- `contribution_share`;
- `previous_score`;
- `score_change`;
- warnings and reason codes.

Missing or invalid component inputs are represented as warnings and conservative review states, not as aggressive assumptions.

## Parameter Sensitivity

`run_sector_component_sensitivity` evaluates configured weight sets against the same snapshots and historical returns. It may rank parameter sets for review, but every sensitivity result has `approved_for_production=False`.

The highest historical return must not be promoted automatically. Parameter selection requires separate review and approval outside this diagnostic path.

## Regime And Stress Breakdown

`calculate_regime_stress_breakdown` groups period records by supplied regime labels and configured stress periods. Missing regime labels are assigned to an `UNKNOWN` diagnostic bucket with a `MACRO_REGIME_MISSING` warning.

Stress periods come only from configuration. The backtest does not invent stress regimes.

## Output Contract

`SectorComponentBacktestResult` contains:

- `metric_summaries`;
- `attribution_rows`;
- `sensitivity_results`;
- `regime_breakdowns`;
- `status`;
- `reason_codes`;
- `warnings`;
- tracking fields: `sector_id`, `as_of_date`, `available_at`, `parameter_version`, `model_version`, `data_snapshot_id`.

The output intentionally does not contain account IDs, order candidates, order instructions, broker fields, or execution fields.

## Scoped UI And API Contract

The structural UI/API scope is documented in `docs/backtests/SECTOR_COMPONENT_BACKTEST_STRUCTURAL_SPEC.md`.

Sector component diagnostics use separate endpoints and do not modify the existing `POST /api/backtests/run` payload or response:

- `GET /api/backtests/sector-components/ui-metadata`;
- `POST /api/backtests/sector-components/run`.

`전체 섹터` means `independent_enabled_sector_backtests`: enabled sector portfolios are backtested independently and returned as comparison rows. It does not mean a combined sector rotation portfolio, best-sector selector, allocation target, or production parameter promotion path.

Scoped run responses carry audit metadata:

- `parameterVersion`;
- `modelVersion`;
- `dataSnapshotId`;
- `reasonCodes`;
- `warnings`.

## Warnings And Conservative Fallback

Conservative statuses are `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, and `RISK_REDUCE_ONLY`. The sector component backtest uses `REVIEW_REQUIRED` when uncertainty is detected.

Examples:

- missing component input: `COMPONENT_REQUIRED_INPUT_MISSING`;
- missing historical return: `HISTORICAL_RETURN_MISSING`;
- low-quality component input: `SECTOR_COMPONENT_LOW_DATA_QUALITY`;
- missing regime label: `MACRO_REGIME_MISSING`;
- fragile parameter grid: `PARAMETER_FRAGILITY`.

## Validation

The current E2E fixture verifies raw fixture loading, config parsing, leakage-safe snapshots, attribution, sensitivity diagnostics, regime/stress breakdowns, conservative warnings, tracking field propagation, and absence of account/order/execution output.

```bash
pytest tests/backtest/test_sector_component_backtest_e2e.py -q
pytest tests/backtest/test_sector_component_scope_backtest_e2e.py -q
pytest tests/unit/features/backtests -q
pytest tests/features/backtests -q
pytest tests/architecture -q
```
