# ADR: Sector Component UI Scope

## Status

Accepted for the sector component structural UI/scope batch.

## Context

The backtests page needs a sector component diagnostic entry point without changing the existing general `/api/backtests/run` flow. The current taxonomy contains only `SEMICONDUCTOR`, `POWER_GRID`, and `BATTERY`, so the first implementation should stay inside that universe.

## Decision

`전체 섹터` means `independent_enabled_sector_backtests`.

For `sector_scope.mode = all`, the system will run each enabled sector portfolio independently and return:

- one scoped result per enabled sector;
- comparison rows for UI display;
- aggregate warnings and reason codes.

`전체 섹터` does not mean:

- a combined sector sleeve;
- a sector rotation portfolio;
- highest-return sector selection;
- automatic allocation or production parameter promotion.

## First Sector Universe

The first implementation uses only the current taxonomy sectors:

- `SEMICONDUCTOR`
- `POWER_GRID`
- `BATTERY`

Missing future themes such as robot, bio, defense, shipbuilding, or AI software are not created by this batch.

## Sector Portfolio Meaning

Sector portfolios are diagnostic sector sleeve fixtures. They support comparable backtest diagnostics and UI metadata only.

They are not:

- account strategy rules;
- target allocations;
- hard constraints;
- order candidates;
- broker execution instructions.

## API Boundary

The existing `POST /api/backtests/run` endpoint remains unchanged.

Sector component diagnostics use separate endpoints:

- `GET /api/backtests/sector-components/ui-metadata`
- `POST /api/backtests/sector-components/run`

## UI Boundary

The backtests page may add a separate sector diagnostic panel. The existing general backtest form, run button, payload, and saved run history remain unchanged.

## Deferred Decisions

Integrated sector rotation portfolios are deferred. If needed later, they should use a separate `portfolio_scope` or `rotation_mode` contract rather than overloading `sector_scope.mode = all`.

Multi-sector selection is also deferred. The first contract supports only `all` and `single`.

## Conservative Fallback

If a requested sector is unknown, a provider is unavailable, historical data is missing, or a diagnostic result cannot be trusted, the response should use conservative status such as `REVIEW_REQUIRED`, `HOLD`, `NO_ACTION`, or `RISK_REDUCE_ONLY`.
