# Intraday Monitoring Test Report

## Test Files Added

- `tests/test_intraday_config_universe.py`
- `tests/test_intraday_repository.py`
- `tests/test_intraday_collector.py`
- `tests/test_intraday_event_detector.py`
- `tests/test_intraday_alert_engine.py`
- `tests/test_intraday_api.py`
- `tests/test_intraday_strategy_isolation.py`

## Commands Run

- `.venv/bin/python -m pytest -q tests/test_intraday_config_universe.py`
- `.venv/bin/python -m pytest -q tests/test_intraday_repository.py`
- `.venv/bin/python -m pytest -q tests/test_intraday_collector.py`
- `.venv/bin/python -m pytest -q tests/test_intraday_event_detector.py`
- `.venv/bin/python -m pytest -q tests/test_intraday_alert_engine.py`
- `.venv/bin/python -m pytest -q tests/test_intraday_api.py`
- `.venv/bin/python -m pytest -q tests/test_intraday_config_universe.py tests/test_intraday_repository.py tests/test_intraday_collector.py tests/test_intraday_event_detector.py tests/test_intraday_alert_engine.py tests/test_intraday_api.py tests/test_intraday_strategy_isolation.py`
- `.venv/bin/python -m pytest -q`

## Status

All commands above passed at the time of this report. The grouped intraday suite reported 58 passed. The final full non-live suite reported 390 passed and 2 skipped. Live broker/order execution tests were not added or required.

## Coverage Notes

- Config, universe resolution, SQLite schema, repository functions, collector behavior, event detection, alert deduplication, API endpoints, and strategy isolation are covered.
- Data quality coverage includes invalid price rejection, stale data warning, missing lookback warning, partial provider failure, and repository write failure.
- A bounded 100-symbol detector fixture is included as a non-timing performance sanity check.

## Deferred Items

- Holiday calendar handling is deferred. Unknown holiday state remains non-trading and monitoring-only.
- External notification delivery is deferred; intraday alerts are stored as internal alert-ready rows.
- Live price query coverage remains gated by existing live-test environment variables and is not required for non-live validation.

## Strategy And Order Boundary

Intraday monitoring remains isolated from macro regime scoring, sector scoring, risk budget, allocation, rebalancing, order draft generation, broker submission, and execution behavior. Intraday events are persisted for display and alert review only.
