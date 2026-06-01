# Sector Component Backtest Structural Spec

## Scope

Sector component scoped backtests are diagnostic-only backtests for comparing enabled sector sleeves. They do not change the existing general portfolio backtest flow and do not create account-specific recommendations, order candidates, broker instructions, or live execution output.

The existing endpoint remains unchanged:

```text
POST /api/backtests/run
```

Sector component diagnostics use separate endpoints:

```text
GET /api/backtests/sector-components/ui-metadata
POST /api/backtests/sector-components/run
```

## Scope Semantics

The `all` mode has exactly one meaning:

```text
independent_enabled_sector_backtests
```

In `all` mode, each enabled sector portfolio is backtested independently and returned as a comparison row plus a child sector result. It is not a combined sector portfolio, a rotation strategy, a highest-return selector, or a production allocation recommendation.

The `single` mode runs one enabled sector portfolio by `sectorId`. Unknown or disabled sectors must fail conservatively through validation or a `REVIEW_REQUIRED` result.

## Current Sector Universe

The current structural batch uses the configured taxonomy sectors only:

- `SEMICONDUCTOR`
- `POWER_GRID`
- `BATTERY`

Missing future sectors are not invented by this path. If a future sector requires a diagnostic sleeve, it should be added through taxonomy, config, tests, and documentation together.

## Portfolio Config

Diagnostic sector sleeve fixtures are loaded from:

```text
config/backtests/sector_component_sector_portfolios.yaml
```

Each sector portfolio is a reproducible fixture for diagnostics and UI metadata. It is not an account target, hard constraint, trading instruction, or approved production sleeve.

## API Contract

`GET /api/backtests/sector-components/ui-metadata` returns:

- `parameterVersion`
- `modelVersion`
- `allSectorOption`
- `sectorOptions`
- `warnings`
- `reasonCodes`

`POST /api/backtests/sector-components/run` accepts:

```json
{
  "sectorScope": {
    "mode": "all"
  }
}
```

or:

```json
{
  "sectorScope": {
    "mode": "single",
    "sectorId": "SEMICONDUCTOR"
  }
}
```

The run response returns:

- `sectorScope`
- `semantics`
- `parameterVersion`
- `modelVersion`
- `dataSnapshotId`
- `status`
- `comparisonRows`
- `sectorResults`
- `warnings`
- `reasonCodes`

The response must not expose account, order, broker, or execution fields.

## UI Contract

The backtests page contains a separate sector component diagnostic panel. The general backtest form, general run button, saved run history, and `BacktestRunRequest` payload remain independent.

The diagnostic panel:

- loads metadata on mount;
- shows `전체 섹터` first;
- shows enabled individual sector options;
- calls the sector component run endpoint with the selected scope;
- shows warning tone for non-`OK` status;
- displays comparison rows, warnings, reason codes, and audit metadata.

## Conservative Fallback

Uncertain inputs should not be guessed. Missing provider data, missing historical returns, unknown sectors, low quality inputs, or unavailable dependencies should resolve to validation failure or conservative status such as `REVIEW_REQUIRED`, `HOLD`, `NO_ACTION`, or `RISK_REDUCE_ONLY`.

## Required Validation

```bash
pytest tests/unit/features/backtests -q
pytest tests/features/backtests -q
pytest tests/backtest/test_sector_component_scope_backtest_e2e.py -q
pytest tests/architecture -q
```
