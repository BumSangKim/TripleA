# Current Structure Inventory

Task: `001_inspect_current_structure_and_boundaries.md`  
Phase: modular-monolith-refactor  
Scope: inspection-only, no code/config/test changes

Updated through legacy cleanup Task 008 after the manifest, trade-data
relocation, score-store relocation, strategy engine decoupling, and root
macro/bottleneck data service cleanup. The original discovery counts below are
retained as historical inspection evidence; source file inventories are
normalized where later tasks changed ownership.

## Preconditions Read

- `AGENTS.md`
- `docs/MASTER_DEVELOPMENT_GUIDE.md`
- `README.md`
- `docs/ARCHITECTURE_CONTRACT.md`
- `.importlinter`
- `DevelopPlans/STATUS.md`

Note: `MASTER_DEVELOPMENT_GUIDE.md` currently exists at `docs/MASTER_DEVELOPMENT_GUIDE.md`.

## Structure Commands

Executed:

```bash
find api -maxdepth 3 -type f | sort
find tests -maxdepth 3 -type f | sort
find config -maxdepth 3 -type f | sort
```

Observed counts:

- `api`: 459 files, including generated `__pycache__` artifacts.
- `tests`: 408 files, including generated `__pycache__` artifacts.
- `config`: 40 files.

Generated cache artifacts are not treated as source-of-truth architecture files.

## api Top-Level Files

```text
api/__init__.py
api/asset_data_requirements.py
api/asset_universe_loader.py
api/asset_universe_mapping.py
api/asset_universe_schema.py
api/asset_universe_snapshot.py
api/asset_universe_validator.py
api/backtest_engine.py
api/backtest_foundation.py
api/data_contracts.py
api/macro_indicator_collector.py
api/macro_telegram_report.py
api/main.py
api/market_data_collector.py
api/market_data_service.py
api/observation_universe.py
api/strategy_config.py
api/telegram_service.py
```

`api/main.py` and `api/__init__.py` are entry/package files, not orphan candidates.

## Feature Slice Matrix

| Feature | router.py | service.py | repository.py | ports.py | schemas.py | models.py | Notes |
|---|---:|---:|---:|---:|---:|---:|---|
| accounts | yes | yes | yes | yes | yes | yes | complete slice shape |
| alerts | yes | yes | yes | yes | yes | yes | complete slice shape |
| auth | yes | yes | yes | yes | yes | yes | complete slice shape |
| backtests | yes | yes | yes | yes | yes | yes | complete slice shape |
| calendar | yes | yes | yes | yes | yes | yes | complete slice shape |
| capex_cycle | yes | yes | yes | yes | yes | yes | complete slice shape |
| dashboard | yes | yes | yes | yes | yes | yes | complete slice shape |
| data_status | yes | yes | yes | yes | yes | yes | complete slice shape |
| documents | yes | yes | yes | yes | yes | yes | complete slice shape |
| holdings | yes | yes | yes | yes | yes | yes | complete slice shape |
| intraday | yes | no | yes | no | no | yes | intentionally different or incomplete; owner review required before enforcing full slice shape |
| macro | yes | yes | yes | yes | yes | yes | complete slice shape |
| market_data | yes | yes | yes | yes | yes | yes | complete slice shape |
| orders | yes | yes | yes | yes | yes | yes | complete slice shape |
| rebalancing | yes | yes | yes | yes | yes | yes | complete slice shape |
| search | yes | yes | yes | yes | yes | yes | complete slice shape |
| strategy | yes | yes | yes | yes | yes | yes | complete slice shape |
| system | yes | yes | yes | yes | yes | yes | complete slice shape |
| targets | yes | yes | yes | yes | yes | yes | complete slice shape |

`api/features/__pycache__/` exists locally as generated cache and is not a feature.

## score_pipeline Files

Source files:

```text
api/score_pipeline/__init__.py
api/score_pipeline/audit.py
api/score_pipeline/backtest.py
api/score_pipeline/contracts.py
api/score_pipeline/data_quality.py
api/score_pipeline/engines.py
api/score_pipeline/features.py
api/score_pipeline/parameters.py
api/score_pipeline/pipeline_manifest.py
api/score_pipeline/plugins/ai_capex_cycle.py
api/score_pipeline/plugins/bio_capex_bottleneck.py
api/score_pipeline/plugins/capex_common.py
api/score_pipeline/plugins/capex_scenario.py
api/score_pipeline/plugins/valuation_engine.py
api/score_pipeline/scoring.py
api/score_pipeline/score_store.py
```

Generated `api/score_pipeline/__pycache__/` files are present locally.

## strategy Files

Source files:

```text
api/strategy/__init__.py
api/strategy/account_constraints/__init__.py
api/strategy/account_constraints/audit.py
api/strategy/account_constraints/config.py
api/strategy/account_constraints/eligibility.py
api/strategy/account_constraints/engine.py
api/strategy/account_constraints/fallbacks.py
api/strategy/account_constraints/models.py
api/strategy/adaptive_offsets.py
api/strategy/allocation_offsets.py
api/strategy/audit_layer.py
api/strategy/bottleneck_sector_engine.py
api/strategy/common_sector_scoring_engine.py
api/strategy/decision_logger.py
api/strategy/indicator_plugins/__init__.py
api/strategy/indicator_plugins/base.py
api/strategy/indicator_plugins/bottleneck_plugin.py
api/strategy/indicator_plugins/registry.py
api/strategy/macro_distribution.py
api/strategy/macro_engine.py
api/strategy/order_candidates.py
api/strategy/phase_engines.py
api/strategy/regime_response_engine.py
api/strategy/risk_budget_engine.py
api/strategy/score_contract.py
api/strategy/score_layer.py
api/strategy/sector_allocation_pressure.py
api/strategy/sector_score_aggregator.py
api/strategy/sector_tilt_engine.py
api/strategy/state_features.py
api/strategy/trade_data_ports.py
api/strategy/triplea_allocator.py
api/strategy/types.py
```

Generated `api/strategy/**/__pycache__/` files are present locally.

## api Root Orphan Candidates

These are root-level source files outside the declared feature, strategy, score_pipeline, db, provider, broker, data, market_data, optimization, and core/domain directories. This inventory does not assign ownership unless it is already clear.

| File | Candidate classification | Notes |
|---|---|---|
| `api/asset_data_requirements.py` | `owner_unresolved` | Asset-universe metadata helper; may belong to data/universe config boundary. |
| `api/asset_universe_loader.py` | `owner_unresolved` | Universe loading; possible data/config owner. |
| `api/asset_universe_mapping.py` | `owner_unresolved` | Universe mapping; possible data/config owner. |
| `api/asset_universe_schema.py` | `owner_unresolved` | Universe schema; possible domain/config contract owner. |
| `api/asset_universe_snapshot.py` | `owner_unresolved` | Universe snapshot/export; possible data owner. |
| `api/asset_universe_validator.py` | `owner_unresolved` | Universe validation; possible data/config owner. |
| `api/backtest_engine.py` | top-level engine | Existing declared engine; do not relocate without explicit task. |
| `api/backtest_foundation.py` | top-level engine support | Existing declared backtest support; do not relocate without explicit task. |
| `api/data_contracts.py` | shared contract | Cross-layer data contract; owner should be kept explicit. |
| `api/macro_indicator_collector.py` | `owner_unresolved` | Collector; likely data collection boundary. |
| `api/macro_telegram_report.py` | `owner_unresolved` | Reporting/notification helper; possible alerts/documents boundary. |
| `api/market_data_collector.py` | `owner_unresolved` | Collector; likely market_data/data boundary. |
| `api/market_data_service.py` | `owner_unresolved` | Root market data service; possible `api/features/market_data` or `api/market_data` owner. |
| `api/observation_universe.py` | shared contract/config | Used for score-flow observation taxonomy; owner should remain explicit. |
| `api/strategy_config.py` | shared config loader | Shared config loading for strategy; moving requires broad import audit. |
| `api/telegram_service.py` | `owner_unresolved` | Notification service; possible alerts owner. |

No owner is finalized here. Files marked `owner_unresolved` require a later task or explicit architecture decision.

## Strategy SQLite / DB Coupling Candidates

No direct strategy SQLite, DB module, root data service, feature module, or
concrete strategy data reader imports remain in `api/strategy/**`.

Resolved during this batch:

- Root trade snapshot service moved to `api/features/market_data/trade_data_service.py`.
- Bottleneck sector engine no longer imports `sqlite3` or the root trade-data
  service; it consumes `TradeSnapshot` / `TradeSnapshotReader`.
- Legacy score-store helper moved to `api/score_pipeline/score_store.py`.
- Macro snapshot reads moved to `api/data/macro_snapshot_reader.py` and are
  injected through strategy data reader ports.
- Bottleneck snapshot and sector mapping reads moved to
  `api/data/bottleneck_snapshot_reader.py` and are injected through strategy
  data reader ports.

## Existing Import Contract Enforcement

`.importlinter` currently declares:

- `api.domain` must not import FastAPI, Starlette, sqlite3, `api.db`, or `api.features`.
- `api.strategy` must not import `api.features`, FastAPI, or Starlette.
- `api.db` must not import `api.features`.
- `api.features` must not import `api.db` according to the configured contract name `router_no_repository`.

`tests/architecture/test_import_contracts.py` currently enforces:

- feature routers do not directly import `api.db`;
- feature routers do not directly import repository modules;
- feature services do not import FastAPI/HTTPException/get_conn/sqlite3;
- `api/domain` does not import FastAPI or DB concerns.

`tests/architecture/test_feature_contracts.py` currently enforces:

- feature services do not import `HTTPException`, `get_conn`, or `sqlite3`;
- feature repositories do not import FastAPI/HTTPException;
- feature services and repositories contain at least one class when present.

`tests/architecture/test_capex_import_boundaries.py` currently enforces:

- capex plugin/feature files do not import broker/order/strategy paths;
- capex source files do not reference live execution symbols;
- registered capex routes remain read-only GET/HEAD routes.

## Remaining Gaps

- Root-level `api/*.py` ownership is now allowlist-enforced but several files
  remain `owner_unresolved`.
- Service-layer tests do not detect every raw SQL string pattern; they focus on
  `sqlite3`, `get_conn`, FastAPI, and HTTPException.
- Router/repository import checks are useful but narrower than a full
  module-boundary graph.
- `api/features/intraday` does not match the complete
  router/service/repository/ports/schemas/models shape, but this inventory does
  not decide whether that is intentional.

## Do Not Touch Without Explicit Approval

- Live broker/KIS paths and account execution behavior.
- Order submission and automatic execution behavior.
- Existing strategy score formulas, macro regime logic, sector scoring logic, risk budget logic, allocation logic, rebalancing logic, and order candidate behavior.
- `api/backtest_engine.py` and established backtest behavior unless a task explicitly allows it.
- Public API behavior of existing routes unless a task explicitly requires a backward-compatible extension.
- Generated cache directories and local-only runtime artifacts.

## Baseline Tests

Executed with `.venv/bin/python` because the repository shell does not expose a plain `python` command.

```bash
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/unit tests/integration -q
```

Latest legacy-cleanup architecture result:

- `tests/architecture`: 47 passed, 2 xfailed.

Later tasks added manifest, architecture, and input-to-output validation tests.
See `docs/PIPELINE_MANIFEST_CONTRACT.md` for the current command set.
