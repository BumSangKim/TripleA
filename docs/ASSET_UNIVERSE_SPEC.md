# Asset Universe Spec

## 1. Purpose

Phase Pre-3 defines the investable and monitorable universe with one normalized asset master and condition-based selectors. This gives backtests, audits, price queries, and future data pipelines a reproducible asset source without enabling live execution.

## 2. Why Duplicate Role Buckets Are Not Used

Duplicate role buckets make one asset appear in several hand-maintained lists, which increases drift and unclear precedence. TripleA now defines each asset once in `config/universe/asset_master.yml`; selectors derive views from asset metadata.

## 3. `asset_master.yml` Single Ledger

`config/universe/asset_master.yml` is the single source of truth for asset identity and metadata. Each asset has one `asset_id`, `symbol`, `market`, `asset_type`, `listing_country`, `base_currency`, `tradability`, `exposures`, `features`, `strategy_roles`, `account_eligibility`, `data_requirements`, and `risk_tags`.

## 4. Metadata Meaning

- `features`: normalized capability and candidate flags used by selectors, such as `core_candidate`, `price_query_required`, and sector/theme exposure markers.
- `exposures`: structured asset-class, region, sector, theme, and currency exposure metadata.
- `strategy_roles`: descriptive strategy roles for audit and future scoring references; they are not duplicate source-of-truth buckets.
- `risk_tags`: conservative risk labels used to exclude blocked or review-heavy products.

## 5. `universe_selectors.yml` Condition-Based Selection

`config/universe/universe_selectors.yml` resolves universes by conditions over asset metadata. Supported conditions include list `all`/`any`, scalar equality, and nested `tradability` checks. Selectors must not use `asset_ids` buckets.

## 6. Resolved Snapshot Need

Feature selectors are flexible, but backtests and audit trails need fixed point-in-time inputs. `scripts/generate_universe_snapshot.py` writes resolved YAML snapshots under `config/universe/snapshots/` for reproducibility.

## 7. ETF Candidates And `monitor_only` Stocks

ETF order-candidate universes are limited to ETF assets with `tradability.order_candidate: true`. Individual stocks are retained only as scoring or monitoring references and must remain `tradability.order_candidate: false` with `enabled_state: monitor_only`.

## 8. Account Eligibility And Hard Constraints

`account_eligibility` records conservative eligibility metadata by account type. It supports hard-constraint checks but does not replace the Phase 2 account constraint engine. Missing or uncertain eligibility should remain `review_required` rather than being assumed eligible.

## 9. Initial `enabled_state` Policy

Initial trade-adjacent ETF candidates use conservative states such as `disabled_until_backtested`. No asset should begin in `enabled_for_order_candidate_after_approval`; any activation must come through an explicit future task and backtest/audit gate.

## 10. Blocked Product Policy

Assets with blocked risk tags such as `leveraged`, `inverse`, `futures_direct`, `options_direct`, or `crypto_direct` are not allowed in the asset master. Selectors also exclude these tags defensively.
