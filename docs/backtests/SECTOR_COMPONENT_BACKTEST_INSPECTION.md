# Sector Component Backtest Inspection

## Scope

This inspection records the current backtest, sector scoring, score contract, point-in-time guard, and test structure before adding sector component backtest diagnostics.

No source code was changed for this inspection. The planned extension should stay inside the existing `api/features/backtests` feature boundary and should not modify account, order, broker, execution, or account-constraint behavior.

## Confirmed Backtest Boundary

- `api/features/backtests/router.py`: FastAPI route boundary for existing backtest run/list/detail endpoints. It depends on `BacktestsService` and does not import the repository directly.
- `api/features/backtests/service.py`: thin orchestration service. Current public methods forward to the repository: `run_backtest`, `list_runs`, `get_run`, `get_decisions`, `get_positions`, and `get_trades`.
- `api/features/backtests/ports.py`: repository protocol for the service boundary.
- `api/features/backtests/models.py`: small dataclass style model file; currently only `BacktestRunParams`.
- `api/features/backtests/schemas.py`: Pydantic request/response contracts for the existing public API.
- `api/features/backtests/repository.py`: persistence-backed backtest implementation. It validates request options, constructs `TripleAAllocator`, checks/collects market data coverage, runs `BacktestEngine`, persists run points/positions/trades/decisions, and returns response schemas.
- `api/backtest_engine.py`: engine-level portfolio simulation over market prices and allocation decisions.

The existing service is an orchestration boundary; strategy scoring formulas and persistence details are not implemented inside `service.py`.

## Confirmed Sector And Score Structure

- `api/strategy/score_contract.py`: strategy-local score contract utilities. It defines `ScoreComponent`, `ScoreSignal`, `clamp_score`, `safe_weighted_average`, `confidence_adjusted_score`, and `combine_reason_codes`.
- `api/strategy/sector_score_aggregator.py`: combines common sector score and plugin scores into `AggregatedSectorScore`.
- `api/strategy/common_sector_scoring_engine.py`: common sector score generation.
- `api/strategy/sector_tilt_engine.py`: applies sector tilt to existing asset weights from sector scores or allocation pressure. This is strategy behavior and should not be modified by the sector component backtest diagnostic work.
- `api/strategy/types.py`: contains `SectorBottleneckScore` and allocation decision contracts used by allocator/backtest decisions.
- `config/sector_taxonomy.yaml`, `config/sector_scoring.yaml`, and `config/allocation_ranges.yaml`: existing sector-related configuration sources.

The new sector component backtest work should consume historical component observations and existing score-style fields as diagnostic input. It should not change `api/strategy/*` behavior.

## Point-In-Time And Availability Guard

- `api/plugin_boundary/time_guard.py` provides `is_available_for_decision(value, decision_time)` and `filter_available_values(values, decision_time)`.
- The guard requires `available_at` and filters out values with `available_at > decision_time`.

This is the reusable availability rule for leakage-safe snapshot building.

## Test Structure

Existing paths:

- `tests/architecture`
- `tests/backtest`
- `tests/features/backtests`
- `tests/strategy`

Requested but not present:

- `tests/unit/features/backtests`
- `tests/unit/strategy`

New task files request `tests/unit/features/backtests`. Creating that directory is a narrow test-organization addition and does not require a top-level architecture layer.

## Config And Tooling

- `pytest.ini` defines `testpaths = tests`, `pythonpath = .`, and `addopts = --import-mode=importlib`.
- `.importlinter` exists and enforces domain purity, strategy no-features imports, db no-features imports, and router no-repository/db imports.
- `pyproject.toml` is not present in this repository.

## Reusable Types And Functions

- Dataclasses are used in `api/features/backtests/models.py` and strategy contracts.
- Pydantic is used for public API schemas in `api/features/backtests/schemas.py`.
- The sector component diagnostic contracts can use dataclasses because they are internal feature contracts and do not change the router/API response model.
- `api.plugin_boundary.time_guard.filter_available_values` can be reused for availability filtering.
- Existing `BacktestsService` can be extended with a separate method in a later task without changing existing route methods.

## Candidate New Files

- `api/features/backtests/sector_component_models.py`
- `api/features/backtests/sector_component_config.py`
- `api/features/backtests/sector_component_dataset.py`
- `api/features/backtests/sector_component_attribution.py`
- `api/features/backtests/sector_component_sensitivity.py`
- `api/features/backtests/sector_component_breakdown.py`
- `api/features/backtests/sector_component_runner.py`
- `tests/unit/features/backtests/*`
- `tests/backtest/test_sector_component_backtest_e2e.py`
- `docs/backtests/SECTOR_COMPONENT_BACKTEST_SPEC.md`

## Public API Impact

No public API change is required for the planned internal runner and service-level integration. Router/API contract changes are not required by the current task pack and should not be introduced.

## Architecture Change Assessment

No architecture change is required. The safest path is to add diagnostic sector component backtest files under the existing `api/features/backtests` boundary, keep strategy behavior untouched, and use fake ports/fixtures in tests.

## Risks And Guardrails

- Sector component diagnostics must not become a threshold switch or direct allocation rule.
- Parameter sensitivity results must not auto-promote the highest-return parameter set.
- Missing or low-quality component data should produce `REVIEW_REQUIRED`, `HOLD`, or validation warnings rather than risk-increasing output.
- Account, order, broker, execution, and account-constraint paths remain out of scope.

## Implementation Follow-Up

Tasks 002 through 010 added the diagnostic contracts, config parser, leakage-safe snapshot builder, attribution calculator, sensitivity runner, regime/stress breakdown, independent runner, service-level injection point, and E2E fixture validation.

The detailed contract is now maintained in `docs/backtests/SECTOR_COMPONENT_BACKTEST_SPEC.md`; the engine-level pointer is `docs/BACKTEST_ENGINE_SPEC.md`.

Validation commands:

```bash
pytest tests/backtest/test_sector_component_backtest_e2e.py -q
pytest tests/unit/features/backtests -q
pytest tests/architecture -q
```
