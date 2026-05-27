# Data Pipeline Spec

## Purpose

Phase 3 builds the raw data pipeline for TripleA. It prepares reliable market, macro, FX, and current quote data for later feature and score layers without creating investment decisions.

## Storage Boundaries

- `raw_data`: Phase 3 scope. External observations, provider metadata, as_of_date, source, updated_at, and quality metadata.
- `feature_data`: Phase 4+ scope. Derived features only after raw data is validated.
- `score_data`: Later scope. Normalized score flow, confidence, and smoothing outputs.
- `decision_data`: Later scope. Allocation, rebalancing, and order-candidate audit outputs.

Phase 3 implements `raw_data` and `data_quality` only.

## Required Metadata

Every persisted raw record should carry enough audit metadata to answer when the value was observable:

- `as_of_date`
- `source`
- `updated_at`
- `quality_score`
- `missing_ratio`
- `is_stale`

Where applicable, monthly or quarterly macro data must also preserve `release_date`. Monthly/quarterly values must not be treated as real-time data.

## Dataset Categories

- `market_price_daily`
- `current_price_quote`
- `macro_indicator`
- `fx_rate`
- `interest_rate`
- `export_import`
- `account_snapshot_reference`

## As-Of And Future Data Policy

Backtests and later feature generation must query only data observable at the requested decision date. Data whose `date`, `release_date`, or `as_of_date` is after the decision date must be excluded to avoid future leakage.

## Provider Boundary

External providers and DB write paths are separated. Providers return typed observations. Repositories persist validated raw observations. Mock provider implementations must support offline tests.

Provider failure must not increase risk or produce a buy/sell decision. It records failed ingestion and conservative quality metadata.

## Backfill Principles

Backfill commands specify dataset, date range, provider, and source/universe. Repeated backfills must be idempotent by using stable upsert keys. Dry-run mode must not write DB records.

## Conservative Fallback

If data is missing, stale, anomalous, or source confidence is unclear, downstream policy is limited to `hold`, `review_required`, `risk_reduce_only`, `reduce_signal_weight`, or `use_conservative_fallback`.
