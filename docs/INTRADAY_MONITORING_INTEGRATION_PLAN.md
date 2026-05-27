# Intraday Monitoring Integration Plan

## 1. Current Repository Structure Relevant To Intraday Monitoring

- Backend entry point: `api/main.py` with a single FastAPI `app`.
- DB setup: `api/db.py` uses SQLite and `ensure_dashboard_tables()` with create-if-not-exists SQL.
- Market data/provider code: `api/market_data/price_provider.py`, `api/data/providers.py`, and `api/data/check_current_quotes.py`.
- Universe/config loading: `config/universe/asset_master.yml`, `config/universe/universe_selectors.yml`, `api/universe/loader.py`, `api/universe/selector.py`, plus legacy `config/investment_universe.yaml`.
- Tests: `tests/` with pytest and `pytest.ini` setting `pythonpath = .`.
- Documentation: `docs/`.

## 2. Existing Code Entry Points To Reuse

- Register intraday endpoints directly in `api/main.py` following existing route style.
- Use `api/db.get_conn()` and direct `sqlite3.Connection` repository functions.
- Reuse `api.universe` loader/selector for investable universe resolution.
- Reuse read-only current quote/provider concepts; do not call broker order paths.

## 3. Proposed New Modules / Files

- `config/intraday_monitoring.yaml`
- `api/intraday/config.py`
- `api/intraday/universe.py`
- `api/intraday/models.py`
- `api/intraday/repository.py`
- `api/intraday/provider.py`
- `api/intraday/collector.py`
- `api/intraday/detector.py`
- `api/intraday/alert.py`
- `docs/INTRADAY_MONITORING_SPEC.md`
- `docs/INTRADAY_MONITORING_OPERATIONS.md`
- `docs/INTRADAY_MONITORING_TEST_REPORT.md`

## 4. DB Integration Approach

Follow the existing raw SQL pattern. Add create-if-not-exists tables for:

- `intraday_price_snapshot`
- `intraday_event`
- `intraday_alert`

Tests use temporary SQLite DBs and must cover every write path.

## 5. Provider Integration Approach

Use a normalized provider contract for snapshot payloads. Default tests use deterministic mock payloads. Existing KIS/read-only quote paths may be adapted later, but this pack will not require secrets or account permissions.

## 6. API Integration Approach

Add read-only monitoring endpoints under `/api/intraday/...` plus one config-gated manual run-once endpoint. Importing the app must not start collection.

## 7. Test Strategy

Add targeted pytest files:

- `tests/test_intraday_config_universe.py`
- `tests/test_intraday_repository.py`
- `tests/test_intraday_collector.py`
- `tests/test_intraday_event_detector.py`
- `tests/test_intraday_alert_engine.py`
- `tests/test_intraday_api.py`
- `tests/test_intraday_strategy_isolation.py`

Then run full `.venv/bin/python -m pytest -q`.

## 8. Explicit Non-Integration Boundaries

- No strategy score impact.
- No allocation impact.
- No rebalancing impact.
- No order candidate impact.
- No execution impact.

Intraday events are monitoring-only in this phase.

## 9. Risks And Conservative Fallback Behavior

- Provider failures should return partial collection results with warnings.
- DB failures should surface to callers and be covered in repository tests.
- Market-session uncertainty should return no-op or warning, not trading behavior.
- Missing lookback or low-quality data should suppress normal-confidence events.

## 10. Next Task Checklist

- Add intraday config and universe resolver.
- Add DB schema/repository.
- Add mock provider and one-shot collector.
- Add detector and alert dedupe.
- Add FastAPI endpoints.
- Add strategy isolation and regression tests.
