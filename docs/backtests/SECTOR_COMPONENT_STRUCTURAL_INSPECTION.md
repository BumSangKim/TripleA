# Sector Component Structural Inspection

## Current Backtests Boundary

`api/features/backtests/router.py` currently exposes the existing general backtest endpoints:

- `POST /api/backtests/run`
- `GET /api/backtests/runs`
- `GET /api/backtests/runs/{run_id}`
- `GET /api/backtests/runs/{run_id}/decisions`
- `GET /api/backtests/runs/{run_id}/positions`
- `GET /api/backtests/runs/{run_id}/trades`

The existing `/api/backtests/run` path must remain unchanged. Sector component scope work should add separate endpoints instead of changing this payload or response.

## Service And Runner Boundary

`api/features/backtests/service.py` keeps the existing repository-backed methods and already has optional sector component injection points:

- `sector_component_data_provider`
- `sector_component_runner`
- `run_sector_component_backtest(config)`

The service returns conservative `REVIEW_REQUIRED` fallback results when sector component dependencies or historical inputs are missing. It does not import DB, FastAPI, account, order, broker, or execution modules.

`api/features/backtests/sector_component_runner.py` is the existing diagnostic runner. It normalizes observations, returns, and regime records; builds leakage-safe snapshots; calculates attribution; runs parameter sensitivity; builds regime/stress breakdowns; aggregates warnings; and returns `SectorComponentBacktestResult`.

## Current Sector Taxonomy

`config/sector_taxonomy.yaml` currently defines these sectors:

- `SEMICONDUCTOR` with assets `SMH`, `SOXX`
- `POWER_GRID` with asset `XLU`
- `BATTERY` with asset `LIT`

The first UI/scope implementation should use only these taxonomy sectors. New sectors such as robot, bio, defense, shipbuilding, or AI software are out of scope.

## Frontend Boundary

`web/app/backtests/BacktestsPageClient.tsx` currently owns the backtests page client state and the general backtest run button. It calls `api.runBacktest(payload)` and stores general backtest history/results.

Sector component UI should be added as a separate diagnostic panel. It must not change the existing general backtest payload, button behavior, or result history behavior.

`web/package.json` has `lint` and `build` scripts. It has no dedicated frontend test script.

## Existing Test Structure

Relevant current tests:

- `tests/features/backtests/test_router.py`
- `tests/features/backtests/test_service.py`
- `tests/unit/features/backtests/*`
- `tests/backtest/test_sector_component_backtest_e2e.py`
- `tests/architecture/*`

The new scope work should add focused unit, API contract, and E2E tests under these existing test groups. It should not create a new top-level architecture layer.

## Allowed Development Surface

Expected implementation files for later tasks:

- `api/features/backtests/schemas.py`
- `api/features/backtests/ports.py`
- `api/features/backtests/service.py`
- `api/features/backtests/router.py`
- `api/features/backtests/sector_component_scope.py`
- `api/features/backtests/sector_component_portfolios.py`
- `api/features/backtests/sector_component_scope_runner.py`
- `config/backtests/sector_component_sector_portfolios.yaml`
- `web/lib/types.ts`
- `web/lib/api.ts`
- `web/app/backtests/SectorComponentDiagnosticPanel.tsx`
- `web/app/backtests/BacktestsPageClient.tsx`

## Forbidden Development Surface

This batch must not modify account, order, broker, execution, account-constraint, or strategy behavior. It must not modify `api/backtest_engine.py`.

The `all` sector mode means independent enabled sector backtests with comparison rows. It does not mean a combined sector rotation portfolio, best-sector selector, or production allocation recommendation.

## Preservation Requirements

- Keep existing `/api/backtests/run` behavior.
- Keep existing Backtests page run behavior.
- Keep sector component output diagnostic-only.
- Do not create account-specific recommendations, order candidates, broker instructions, or execution output.
- Use conservative fallback states when inputs or rules are uncertain.
