# Phase 1 Asset Universe Audit

## Scope Reviewed

Reviewed Phase 1 asset universe implementation from `TASK_101` through `TASK_109`.

Phase 1 scope was limited to:

- status and guardrails;
- asset universe schema;
- asset universe configuration;
- universe loader;
- universe validator;
- account eligibility metadata;
- sector and asset-class mapping metadata;
- data requirement metadata;
- deterministic snapshot export.

No strategy scoring, macro regime scoring, allocation, rebalancing, order generation, broker integration, live account linking, or order execution behavior was included in Phase 1.

## Files Changed

Phase 1 implementation files:

- `docs/PHASE_1_STATUS.md`
- `docs/PHASE_1_ASSET_UNIVERSE_GUARDRAILS.md`
- `docs/PHASE_1_ASSET_UNIVERSE_AUDIT.md`
- `api/asset_universe_schema.py`
- `api/asset_universe_loader.py`
- `api/asset_universe_validator.py`
- `api/asset_universe_mapping.py`
- `api/asset_data_requirements.py`
- `api/asset_universe_snapshot.py`
- `config/asset_universe.yaml`
- `config/asset_universe_mappings.yaml`
- `config/asset_data_requirements.yaml`
- `tests/test_asset_universe_schema.py`
- `tests/test_asset_universe_config.py`
- `tests/test_asset_universe_loader.py`
- `tests/test_asset_universe_validator.py`
- `tests/test_asset_universe_mapping.py`
- `tests/test_asset_data_requirements.py`
- `tests/test_asset_universe_snapshot.py`

Pre-existing unrelated working tree changes were not reverted or normalized.

## Schema Review

The asset schema exists in `api/asset_universe_schema.py`.

Confirmed properties:

- required asset metadata fields are represented;
- roles, risk tiers, and liquidity tiers are constrained;
- missing required fields raise `AssetUniverseSchemaError`;
- conservative fallback creates disabled, review-required, non-actionable assets;
- `eligible_for_order_candidate` is derived conservatively;
- unknown or missing account eligibility does not become actionable.

The schema is metadata-only and does not calculate scores, weights, trades, or orders.

## Config Review

The initial controlled candidate universe exists at `config/asset_universe.yaml`.

Confirmed properties:

- includes cash, broad domestic equity proxy, broad global equity proxy, defensive bond proxy, satellite sector proxy, and watchlist placeholder;
- each asset declares enabled state, role, risk tier, liquidity tier, account eligibility, data requirements, review requirement, and notes;
- inclusion is documented as not being a buy, overweight, allocation, rebalancing, order-candidate, or execution signal;
- uncertain assets remain `review_required` and/or disabled watchlist assets.

The universe file does not contain target weights, macro regime rules, buy/sell logic, or execution behavior.

## Loader Review

The loader exists in `api/asset_universe_loader.py`.

Confirmed properties:

- reads `config/asset_universe.yaml`;
- converts raw entries into `AssetDefinition` objects;
- exposes all assets, enabled assets, watchlist assets, and lookup by `asset_id`;
- rejects duplicate IDs;
- fails conservatively on missing, malformed, or invalid config through `AssetUniverseLoadError`;
- uses conservative states such as `REVIEW_REQUIRED` and `NO_ACTIVE_UNIVERSE`.

The loader does not create a tradable universe from missing or invalid input.

## Validator Review

The validator exists in `api/asset_universe_validator.py`.

Confirmed properties:

- returns structured validation results;
- separates blocking errors from warnings;
- reports review-required assets;
- exposes active asset count;
- sets conservative state on blocking validation failure;
- catches duplicate IDs, missing required fields, invalid schema values, enabled assets without eligibility, enabled assets without data requirements, and disabled assets marked tradable.

The validator provides safety information only. It does not make investment decisions.

## Account Eligibility Review

Account eligibility metadata is represented in `AssetDefinition.account_eligibility`.

Confirmed properties:

- supports `taxable`, `isa`, `pension`, and `irp`;
- each account entry includes `eligible`, `review_required`, and `restrictions`;
- unknown account types are forced to not eligible and review required;
- missing account eligibility resolves conservatively;
- review-required eligibility prevents automatic downstream action.

This is not a full account constraint engine. Final account/legal/product checks remain a later phase.

## Sector / Asset Class Mapping Review

Canonical mappings exist in `config/asset_universe_mappings.yaml` and `api/asset_universe_mapping.py`.

Confirmed properties:

- canonical asset classes include `cash`, `equity`, `bond`, `commodity`, `real_asset`, `alternative`, `hedge`, and `unknown`;
- canonical sectors include `none`, `broad_market`, `semiconductor`, `robot`, `bio`, `energy`, `financials`, `consumer`, `industrial`, `technology`, and `defensive`;
- aliases normalize only through explicit mapping configuration;
- unknown categories are rejected or retained only as conservative review-required states.

No sector name maps directly to score, allocation, rebalance, buy, or sell behavior.

## Data Requirement Metadata Review

Canonical data requirement metadata exists in `config/asset_data_requirements.yaml` and `api/asset_data_requirements.py`.

Confirmed properties:

- supports keys equivalent to price, volume, FX, rates, macro, trade, sector index, financial statements, ETF holdings, and account balance snapshots;
- enabled assets with no data requirements are invalid;
- enabled assets with unknown requirements are invalid;
- disabled watchlist assets may retain `REVIEW_REQUIRED` as a warning and remain non-actionable;
- data readiness is separate from account eligibility.

No data fetching, feature calculation, scoring, or risk increase is implemented by this metadata.

## Snapshot / Auditability Review

Snapshot export exists in `api/asset_universe_snapshot.py`.

Confirmed properties:

- exports total, enabled, and watchlist asset counts;
- includes validation result;
- includes all assets, including disabled/watchlist assets;
- includes account eligibility and data requirements through serialized asset metadata;
- uses a deterministic content-based `snapshot_id`;
- accepts deterministic `created_at` injection for tests;
- malformed config returns an invalid, non-actionable snapshot rather than an actionable universe.

## Test Results

Final full test command:

```bash
.venv/bin/python -m pytest
```

Final result:

```text
189 passed in 2.73s
```

Phase 1 targeted test coverage includes:

- schema validation;
- config validation;
- loader conservative failures;
- validator errors/warnings;
- account eligibility metadata;
- canonical asset class and sector mapping;
- data requirement metadata;
- deterministic snapshot export.

## Remaining Gaps

These are intentionally outside Phase 1:

- full account constraint engine;
- broker/product eligibility verification against real account data;
- feature layer and score layer contracts;
- backtest integration using Phase 1 snapshot artifacts;
- allocation target ranges;
- rebalancing intensity logic;
- order candidate generation;
- user-approved execution workflow;
- live execution or broker order submission.

Conservative follow-up defaults:

- unknown account eligibility: `REVIEW_REQUIRED`;
- missing data requirements: no active downstream action;
- malformed universe config: `NO_ACTION` / `NO_ACTIVE_UNIVERSE`;
- disabled or watchlist assets: non-actionable.

## Phase 1 Completion Decision

Phase 1 is complete.

All required Phase 1 tasks from `TASK_101` through `TASK_110` are complete, the full test suite passes, and no prohibited live execution, broker order submission, automatic order execution, scoring, allocation, rebalancing, or order-generation behavior was introduced.

