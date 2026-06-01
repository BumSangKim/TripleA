# Backtest Engine Spec

## Scope

The backtest engine area contains read-only simulation and diagnostic validation. It must not submit broker orders, create live execution instructions, or promote parameters automatically.

## Current Backtest Paths

- Existing portfolio backtest API: `api/features/backtests/router.py`, `service.py`, `repository.py`, and `api/backtest_engine.py`.
- Sector component diagnostic backtest: internal feature contracts under `api/features/backtests/sector_component_*.py`.

## Sector Component Backtest

The sector component diagnostic backtest is documented in `docs/backtests/SECTOR_COMPONENT_BACKTEST_SPEC.md`.

It validates component observations through leakage-safe snapshots, attribution rows, parameter sensitivity diagnostics, and regime/stress breakdowns. It is not a strategy execution path and does not produce order candidates, account-specific recommendations, broker instructions, or execution output.

Parameter sensitivity output is diagnostic only. The highest historical-return parameter set must not be adopted automatically.

The scoped sector component UI/API extension is documented in `docs/backtests/SECTOR_COMPONENT_BACKTEST_STRUCTURAL_SPEC.md`. It adds diagnostic metadata and run endpoints separate from the existing general backtest endpoint:

- `GET /api/backtests/sector-components/ui-metadata`
- `POST /api/backtests/sector-components/run`

For that extension, `전체 섹터` means `independent_enabled_sector_backtests`. Each enabled sector sleeve is backtested independently for comparison. A combined sector rotation portfolio is explicitly out of scope.

Scoped responses preserve audit metadata: `parameterVersion`, `modelVersion`, `dataSnapshotId`, `reasonCodes`, and `warnings`.

## Required Checks

```bash
pytest tests/backtest/test_sector_component_backtest_e2e.py -q
pytest tests/backtest/test_sector_component_scope_backtest_e2e.py -q
pytest tests/unit/features/backtests -q
pytest tests/features/backtests -q
pytest tests/architecture -q
```
