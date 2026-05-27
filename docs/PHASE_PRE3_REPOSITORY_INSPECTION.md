# Phase Pre-3 Repository Inspection

## 1. Existing config structure

- `config/asset_universe.yaml`, `config/asset_universe_mappings.yaml`, and `config/asset_data_requirements.yaml` contain Phase 1 asset universe metadata.
- `config/account_constraints.yaml` contains Phase 2 account constraint metadata.
- `config/investment_universe.yaml`, `config/backtest_assets.yaml`, `config/sector_taxonomy.yaml`, and `config/strategy_profiles.yaml` are existing strategy/backtest inputs.
- No `config/universe/asset_master.yml` or selector-based universe config exists yet.

## 2. Existing universe or asset structure

- `api/asset_universe_schema.py`, `api/asset_universe_loader.py`, `api/asset_universe_validator.py`, and related tests provide Phase 1 asset metadata validation.
- `api/market_data_service.py` reads existing DB-backed `asset_universe`, `market_prices`, and `fx_rates` tables for backtests.
- `api/db.py` seeds legacy/current `asset_universe` rows from `config/backtest_assets.yaml` and `config/investment_universe.yaml`.
- These structures are reusable as references, but the Pre-3 asset master should be a new normalized adapter, not a broad replacement.

## 3. Existing price provider

- There is historical market data collection through `api/market_data_collector.py`.
- There is DB-backed price lookup through `api/market_data_service.py`.
- There is no explicit read-only `PriceProvider` contract for live/current quote validation.

## 4. Existing KIS read-only path

- `api/kis.py` provides KIS config, token, and domestic balance parsing/client behavior.
- `api/providers.py` uses KIS for paper/live account sync in read-only mode.
- Existing KIS code is account/balance oriented and should not be expanded to order submission in Pre-3.
- Pre-3 live price tests must not require account password, order permissions, or broker order endpoints.

## 5. Existing DB/session/repository structure

- The repository uses SQLite through `api/db.py::get_conn`; no SQLAlchemy session layer was observed.
- Existing tests monkeypatch temporary DB paths and call `ensure_dashboard_tables`.
- Market price tables already exist for historical prices, but Pre-3 quote persistence should use a small create-if-not-exists table and temporary DB tests.

## 6. Existing test structure

- Root tests live under `tests/`.
- Phase 2 account constraint tests live under `tests/strategy/`.
- Existing market data tests cover schema, historical price lookup, and coverage validation.
- Integration tests can be added under `tests/integration/` and gated by explicit environment variables.

## 7. Reusable module candidates

- `api/asset_universe_loader.PROJECT_ROOT` for stable project-root paths.
- `api/db.py` SQLite style and temporary DB test pattern.
- `api/market_data_service.py` historical price read patterns.
- Phase 2 account constraint module for future account eligibility checks, without wiring it into order generation here.

## 8. New module candidates

- `api/universe/loader.py`, `api/universe/validator.py`, `api/universe/selector.py`, and `api/universe/snapshot.py`.
- `api/market_data/models.py`, `api/market_data/price_provider.py`, and `api/market_data/repository.py`.
- `config/universe/schema.yml`, `config/universe/asset_master.yml`, `config/universe/universe_selectors.yml`, and generated snapshots.

## 9. Changes to avoid

- Do not alter allocation, rebalancing, order candidate, broker/KIS, or execution behavior.
- Do not make duplicate role buckets a source of truth.
- Do not hardcode strategy assets in strategy code.
- Do not touch live order execution, broker order submission, balance/orderable-cash endpoints, account passwords, or automatic trading behavior.
- Do not mutate existing runtime DB data in tests; use temporary DBs for DB write/read validation.
