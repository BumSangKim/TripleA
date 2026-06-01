# Sector Component Backtest Final Validation

## Scope Completed

This validation covers the sector component structural UI/scope batch:

- repository boundary inspection;
- structural ADR for `전체 섹터`;
- scope contracts and public API schemas;
- diagnostic sector portfolio config and loader;
- independent scope runner;
- service and router integration;
- API contract and E2E tests;
- frontend types, API client, and diagnostic panel integration;
- documentation and audit notes.

## Guardrails

- Existing `POST /api/backtests/run` behavior is preserved.
- `전체 섹터` means `independent_enabled_sector_backtests`.
- Integrated sector rotation portfolios are not implemented.
- Sector component portfolios remain diagnostic fixtures only.
- No account strategy, account constraints, order, broker, live execution, or `api/backtest_engine.py` behavior was changed.
- Conservative fallback status remains required for uncertain data or unavailable dependencies.

## Validation Commands

```bash
pytest tests/unit/features/backtests -q
pytest tests/features/backtests -q
pytest tests/backtest/test_sector_component_backtest_e2e.py -q
pytest tests/backtest/test_sector_component_scope_backtest_e2e.py -q
pytest tests/architecture -q
cd web && npm run lint
cd web && npm run build
```

## Validation Results

- `pytest tests/unit/features/backtests -q`: 103 passed.
- `pytest tests/features/backtests -q`: 23 passed.
- `pytest tests/backtest/test_sector_component_backtest_e2e.py -q`: 6 passed.
- `pytest tests/backtest/test_sector_component_scope_backtest_e2e.py -q`: 4 passed.
- `pytest tests/architecture -q`: 17 passed.
- `cd web && npm run lint`: passed.
- `cd web && npm run build`: passed.

## Key Files Changed

- `api/features/backtests/dependencies.py`
- `api/features/backtests/ports.py`
- `api/features/backtests/router.py`
- `api/features/backtests/schemas.py`
- `api/features/backtests/service.py`
- `api/features/backtests/sector_component_portfolios.py`
- `api/features/backtests/sector_component_scope.py`
- `api/features/backtests/sector_component_scope_runner.py`
- `api/features/backtests/sector_component_ui_metadata.py`
- `config/backtests/sector_component_sector_portfolios.yaml`
- `docs/BACKTEST_ENGINE_SPEC.md`
- `docs/backtests/SECTOR_COMPONENT_BACKTEST_SPEC.md`
- `docs/backtests/SECTOR_COMPONENT_BACKTEST_STRUCTURAL_SPEC.md`
- `web/app/backtests/BacktestsPageClient.tsx`
- `web/app/backtests/SectorComponentDiagnosticPanel.tsx`
- `web/lib/api.ts`
- `web/lib/types.ts`

## Test Files Added

- `tests/backtest/test_sector_component_scope_backtest_e2e.py`
- `tests/features/backtests/test_sector_component_api_contract.py`
- `tests/features/backtests/test_sector_component_metadata_endpoint.py`
- `tests/features/backtests/test_sector_component_run_endpoint.py`
- `tests/unit/features/backtests/test_backtest_service_sector_component_scope.py`
- `tests/unit/features/backtests/test_sector_component_portfolio_loader.py`
- `tests/unit/features/backtests/test_sector_component_portfolios_contracts.py`
- `tests/unit/features/backtests/test_sector_component_public_schemas.py`
- `tests/unit/features/backtests/test_sector_component_scope.py`
- `tests/unit/features/backtests/test_sector_component_scope_runner.py`
- `tests/unit/features/backtests/test_sector_component_ui_metadata.py`

## Remaining Risks

- The default service dependency does not inject a production sector component data provider; without an override it returns conservative `REVIEW_REQUIRED` fallback for scoped run data.
- The first sector universe is limited to configured taxonomy sectors: `SEMICONDUCTOR`, `POWER_GRID`, and `BATTERY`.
- Additional future sectors require taxonomy, config, fixture, and contract updates together.

## Commit Message Candidate

```text
backtests: add sector component scope diagnostics
```
