# Phase 3 Data Pipeline Audit

## Existing data sources

- `config/indicators.yaml` lists macro indicator metadata.
- `config/backtest_assets.yaml` and the existing `asset_universe` DB seed support historical market data tests.
- `config/universe/asset_master.yml` is the normalized asset source for Phase Pre-3.
- `config/universe/universe_selectors.yml` resolves asset candidates by metadata conditions.

## Existing DB schema / models

- `api/db.py` owns SQLite setup through `ensure_dashboard_tables()`.
- Existing tables include `market_prices`, `fx_rates`, `asset_universe`, `indicators`, `data_collection_runs`, and dashboard/order/backtest tables.
- Phase Pre-3 added `price_quotes` through `api/market_data/repository.py` for read-only current quote persistence.
- There is no migration framework; current convention is create-if-not-exists schema setup.

## Existing provider interfaces

- `api/kis.py` contains a read-only KIS account/balance client.
- `api/market_data/price_provider.py` contains a read-only current price provider contract and deterministic mock provider.
- `api/market_data_collector.py` contains historical collector helpers for existing `market_prices` / `fx_rates`.

## Existing current price lookup path

- Current quote lookup exists through `api.market_data.price_provider.PriceProvider.get_current_price`.
- Default tests use `MockPriceProvider`.
- Live quote access is gated by explicit environment variables and read-only KIS app credentials.
- No order submission path is part of the current price contract.

## Existing historical data/backfill path

- Existing historical data storage uses `market_prices` and `fx_rates`.
- `scripts/collect_historical_data.py` and `api/market_data_collector.py` provide collection-adjacent behavior.
- A unified Phase 3 raw-data backfill CLI does not yet exist.

## Existing data quality handling

- `api/market_data_service.py` has coverage checks for stale/missing market and FX data.
- There is no general `data_quality_checks` repository yet for raw market, current quote, and macro datasets.

## Missing pieces for Phase 3

- Settings-driven data source registry.
- Raw-data repository layer for price history, current quotes, macro observations, ingestion runs, and quality checks.
- Deterministic mock data providers for offline tests.
- Idempotent ingestion and backfill services.
- As-of data snapshot contract to avoid future-data leakage.
- Read-only status API for data freshness and quality.

## Risks and conservative fallback policy

- Missing provider credentials must skip live checks instead of failing normal tests.
- Missing, stale, or anomalous raw data must produce `review_required`, `hold`, `risk_reduce_only`, or `use_conservative_fallback` metadata only.
- Data quality must never create raw buy/sell, rebalancing, or order-candidate decisions.
