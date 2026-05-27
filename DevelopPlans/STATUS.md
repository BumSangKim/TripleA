# Development Status

## Current Phase

Phases 5-13 pre-execution score-flow foundation completed

## Current Task

None — Phases 5-13 were implemented as pre-execution, test-covered foundations. Live execution and broker order submission remain out of scope.

## Completed Tasks

- New Pipeline Architecture implemented:
  - repository and architecture audit;
  - independent `api/new_pipeline` contracts;
  - versioned parameter registry under `config/parameters/`;
  - data snapshot and quality layer;
  - feature plugin registry;
  - score layer core;
  - macro regime distribution engine;
  - sector scoring engine;
  - risk budget and hard constraint gate;
  - allocation and rebalancing engine;
  - backtest smoke adapter and leakage tests;
  - reporting/audit and review-only order candidates.
- Phase 5 Score Layer implemented:
  - score contract;
  - score definitions;
  - normalization;
  - EMA smoothing;
  - event/manual span override;
  - confidence/data quality adjustment;
  - score persistence;
  - score runner/interface;
  - tests.
- Phase 6 Backtest Engine foundation implemented:
  - simulation contracts;
  - deterministic clock;
  - historical snapshot loader;
  - portfolio state transition;
  - cost/tax hooks;
  - metrics;
  - plug-in runner tests.
- Phase 7 Macro Regime Engine implemented as distribution output, with dominant regime explanation-only.
- Phase 8 Sector Scoring Engine implemented as config-driven decomposable scoring and deterministic ranking.
- Phase 9 Risk Budget Engine implemented with portfolio/account budgets and hard-constraint blocking.
- Phase 10 Allocation Engine implemented with gradual score-linked target ranges and cash residual handling.
- Phase 11 Rebalancing Engine implemented with action semantics and overweight winner policy.
- Phase 12 Reporting/Audit Layer implemented with decision logs, reason/warning catalog, reports, and explanations.
- Phase 13 Order Candidate Generation implemented as non-executable, user-review-only candidates with validation.
- `DevelopPlans/phase0/TASK_000_REPOSITORY_AUDIT.md`
- `DevelopPlans/phase0/TASK_001_PROJECT_GUARDRAILS.md`
- `DevelopPlans/phase0/TASK_002_GAP_ANALYSIS.md`
- `DevelopPlans/phase0/TASK_003_DEVELOPMENT_SEQUENCE.md`
- `DevelopPlans/phase0/TASK_004_ARCHITECTURE_MAP.md`
- `DevelopPlans/phase0/TASK_005_TEST_BASELINE.md`
- `TASK_101_PHASE1_STATUS_AND_GUARDRAILS.md`
- `TASK_102_ASSET_UNIVERSE_SCHEMA.md`
- `TASK_103_ASSET_UNIVERSE_CONFIG.md`
- `TASK_104_UNIVERSE_LOADER.md`
- `TASK_105_UNIVERSE_VALIDATOR.md`
- `TASK_106_ACCOUNT_ELIGIBILITY_METADATA.md`
- `TASK_107_SECTOR_AND_ASSET_CLASS_MAPPING.md`
- `TASK_108_DATA_REQUIREMENT_METADATA.md`
- `TASK_109_UNIVERSE_SNAPSHOT_EXPORT.md`
- `TASK_110_PHASE1_INTEGRATION_AUDIT.md`
- `TASK_000_PHASE2_BASELINE_AUDIT.md`
- `TASK_001_ACCOUNT_CONSTRAINT_SPEC.md`
- `TASK_002_ACCOUNT_CONFIG_SCHEMA.md`
- `TASK_003_ACCOUNT_DOMAIN_MODELS.md`
- `TASK_004_CONSTRAINT_RULE_ENGINE.md`
- `TASK_005_IRP_RISKY_ASSET_LIMIT.md`
- `TASK_006_TRADE_ELIGIBILITY_VALIDATOR.md`
- `TASK_007_CONSERVATIVE_FALLBACKS.md`
- `TASK_008_BACKTEST_COMPATIBILITY.md`
- `TASK_009_REPORTING_AUDIT_INTEGRATION.md`
- `TASK_010_PHASE2_FINAL_VALIDATION.md`
- `TASK_000_REPOSITORY_INSPECTION.md`
- `TASK_001_CREATE_ASSET_MASTER_SCHEMA.md`
- `TASK_002_CREATE_ASSET_MASTER.yml.md`
- `TASK_003_CREATE_UNIVERSE_SELECTORS.md`
- `TASK_004_IMPLEMENT_UNIVERSE_LOADER_AND_VALIDATOR.md`
- `TASK_005_IMPLEMENT_SELECTOR_RESOLVER.md`
- `TASK_006_CREATE_SNAPSHOT_GENERATOR.md`
- `TASK_007_PRICE_PROVIDER_READ_ONLY_CONTRACT.md`
- `TASK_008_LIVE_PRICE_QUERY_SMOKE_TEST.md`
- `TASK_009_MARKET_DATA_DB_SCHEMA.md`
- `TASK_010_DB_WRITE_READ_INTEGRATION_TEST.md`
- `TASK_011_END_TO_END_UNIVERSE_DATA_DB_TEST.md`
- `TASK_012_GUARDRAILS_AND_NO_LIVE_EXECUTION_TESTS.md`
- `TASK_013_DOCUMENTATION_AND_STATUS_UPDATE.md`
- `TASK_300_PHASE3_BASELINE.md`
- `TASK_301_DATA_PIPELINE_SPEC.md`
- `TASK_302_DATA_SOURCE_REGISTRY.md`
- `TASK_303_RAW_DATA_SCHEMA.md`
- `TASK_304_PROVIDER_INTERFACE_AND_MOCKS.md`
- `TASK_305_PRICE_HISTORY_COLLECTION.md`
- `TASK_306_MACRO_DATA_COLLECTION.md`
- `TASK_307_CURRENT_PRICE_CONNECTIVITY.md`
- `TASK_308_DATA_QUALITY_VALIDATION.md`
- `TASK_309_DATA_SNAPSHOT_CONTRACT.md`
- `TASK_310_BACKFILL_CLI_IDEMPOTENCY.md`
- `TASK_311_DATA_STATUS_API.md`
- `TASK_312_PHASE3_INTEGRATION_TEST_AND_CLOSEOUT.md`
- `TASK_000_REPOSITORY_AND_STRATEGY_AUDIT.md`
- `TASK_001_DATA_LAYER_CONTRACTS.md`
- `TASK_002_TESTBED_DATABASE_SCHEMA.md`
- `TASK_003_COMMON_SCORE_CONTRACT.md`
- `TASK_004_OBSERVATION_UNIVERSE_AND_TAXONOMY.md`
- `TASK_005_DATA_QUALITY_AND_SNAPSHOT_SERVICE.md`
- `TASK_006_COMMON_SECTOR_SCORING_ENGINE.md`
- `TASK_007_SPECIALIZED_INDICATOR_PLUGIN_REGISTRY.md`
- `TASK_008_BOTTLENECK_PLUGIN_MIGRATION.md`
- `TASK_009_SECTOR_SCORE_AGGREGATOR.md`
- `TASK_010_SECTOR_ALLOCATION_PRESSURE.md`
- `TASK_011_MACRO_DISTRIBUTION_AND_STATE_FEATURES.md`
- `TASK_012_REGIME_RESPONSE_AND_OFFSETS.md`
- `TASK_013_RISK_BUDGET_OFFSET_INTEGRATION.md`
- `TASK_014_SECTOR_TILT_PRESSURE_INTEGRATION.md`
- `TASK_015_ALLOCATION_REBALANCING_OFFSETS.md`
- `TASK_016_DECISION_LOGGING_AND_SCORE_STORE_INTEGRATION.md`
- `TASK_017_REALIZED_REGIME_LABELER.md`
- `TASK_018_JUDGMENT_BACKTEST_EVALUATOR.md`
- `TASK_019_PARAMETER_SET_AND_OPTIMIZATION_SCHEMA.md`
- `TASK_020_RECURSIVE_OPTIMIZATION_ENGINE_V1.md`
- `TASK_021_ROBUSTNESS_TESTER_AND_FAILURE_ANALYZER.md`
- `TASK_022_OPTIMIZATION_REPORTING_API.md`
- `TASK_023_BACKTEST_ENGINE_INTEGRATION.md`
- `TASK_024_DOCUMENTATION_AND_STATUS.md`
- `TASK_INTRADAY_001_REPOSITORY_AUDIT_AND_INTEGRATION_PLAN.md`
- `TASK_INTRADAY_002_CONFIG_AND_UNIVERSE_RESOLUTION.md`
- `TASK_INTRADAY_003_DB_SCHEMA_AND_REPOSITORY.md`
- `TASK_INTRADAY_004_PROVIDER_AND_ONE_MINUTE_COLLECTOR.md`
- `TASK_INTRADAY_005_SURGE_DROP_EVENT_DETECTOR.md`
- `TASK_INTRADAY_006_ALERT_ENGINE_AND_DEDUPLICATION.md`
- `TASK_INTRADAY_007_MONITORING_API_AND_EXISTING_APP_WIRING.md`
- `TASK_INTRADAY_008_TESTS_VALIDATION_AND_REGRESSION.md`
- `TASK_INTRADAY_009_DOCUMENTATION_AND_HANDOFF.md`

## Blocked Tasks

None

## Partial / Unclear Tasks

- Phase 4 implementation tasks are not started as formal task files in the canonical status.
- Existing legacy/current engine behavior for macro regime, sector tilt, risk budget, allocation, rebalancing, and order candidates remains partial relative to `docs/MASTER_DEVELOPMENT_GUIDE.md`.
- Documentation tree normalization still has a pending approval item: tracked files under `docs/DevelopLog/` and `docs/DevelopPlans/` are currently deleted in the working tree and require an explicit restore/archive/delete decision.

## Last Test Command

```bash
.venv/bin/python -m pytest -q && npm run lint && npm run build
```

## Last Test Result

Passed — 515 passed, 2 skipped in 4.78s; web lint passed; web build passed. `npm test` is not configured in `web/package.json`.

## Intraday Surge/Drop Monitoring

- Status: complete.
- Scope: monitoring display and alert-ready persistence only; no strategy score, allocation, rebalancing, order candidate, broker submission, or live execution integration was added.
- Completed:
  - Repository audit and integration plan.
  - Intraday monitoring config and asset-master-based universe resolution.
  - SQLite schema and repository functions for snapshots, events, and alerts.
  - Read-only provider adapter and one-pass collector.
  - Surge/drop/volume spike detector with monitoring-only thresholds.
  - Alert-ready payload generation and duplicate suppression.
  - FastAPI endpoints under `/api/intraday/*`.
  - Strategy isolation, integration scenario, data-quality, and regression tests.
  - Spec, operations, and test report documentation.
- Major files:
  - `config/intraday_monitoring.yaml`
  - `api/intraday/`
  - `api/main.py`
  - `tests/test_intraday_config_universe.py`
  - `tests/test_intraday_repository.py`
  - `tests/test_intraday_collector.py`
  - `tests/test_intraday_event_detector.py`
  - `tests/test_intraday_alert_engine.py`
  - `tests/test_intraday_api.py`
  - `tests/test_intraday_strategy_isolation.py`
  - `docs/INTRADAY_MONITORING_INTEGRATION_PLAN.md`
  - `docs/INTRADAY_MONITORING_SPEC.md`
  - `docs/INTRADAY_MONITORING_OPERATIONS.md`
  - `docs/INTRADAY_MONITORING_TEST_REPORT.md`
- Test commands:
  - `.venv/bin/python -m pytest -q tests/test_intraday_config_universe.py`
  - `.venv/bin/python -m pytest -q tests/test_intraday_repository.py`
  - `.venv/bin/python -m pytest -q tests/test_intraday_collector.py`
  - `.venv/bin/python -m pytest -q tests/test_intraday_event_detector.py`
  - `.venv/bin/python -m pytest -q tests/test_intraday_alert_engine.py`
  - `.venv/bin/python -m pytest -q tests/test_intraday_api.py`
  - `.venv/bin/python -m pytest -q tests/test_intraday_config_universe.py tests/test_intraday_repository.py tests/test_intraday_collector.py tests/test_intraday_event_detector.py tests/test_intraday_alert_engine.py tests/test_intraday_api.py tests/test_intraday_strategy_isolation.py`
  - `.venv/bin/python -m pytest -q`
- Test result: targeted intraday tests passed with 58 passed; full non-live backend suite passed with 390 passed and 2 skipped.
- Remaining TODO / REVIEW_REQUIRED:
  - Holiday calendar support is deferred.
  - External dashboard notification delivery is deferred.
  - Any future score/risk/rebalancing/order integration requires explicit approval and a separate task.
  - Resolve pre-existing tracked deletions under `docs/DevelopLog/` and `docs/DevelopPlans/`.
- Next recommended task: Phase 4 Feature Layer hardening, or an explicitly approved dashboard notification task that keeps live execution disabled.

## Score-Flow Adaptive Testbed v2

- Status: complete.
- Scope: opt-in testbed infrastructure only; existing default strategy/backtest behavior is preserved.
- Completed:
  - Repository and strategy audit.
  - Data-layer contracts and testbed schema.
  - Common score contract.
  - Observation universe and sector taxonomy support.
  - Data snapshot and quality service.
  - Common sector scoring engine.
  - Specialized indicator plugin registry.
  - Bottleneck logic wrapped as a specialized plugin, not a universal model.
  - Sector score aggregator.
  - Continuous sector allocation pressure.
  - Macro distribution and market/portfolio state features.
  - Regime response engine and adaptive offsets.
  - Optional risk budget, sector tilt, and allocation offset integrations.
  - Decision logging and score store services.
  - Evaluation-only realized regime labeler.
  - Judgment backtest evaluator.
  - Parameter, optimization run, and candidate stores.
  - Recursive optimization v1, robustness tester, failure analyzer, and reporting.
  - Optional backtest request fields for testbed mode.
- Explicit non-goals preserved:
  - No live order execution.
  - No return-only optimization.
  - No automatic parameter promotion.
  - No sector core/satellite hierarchy migration.
  - No bottleneck data universal model.
- Major files:
  - `api/data_contracts.py`
  - `api/testbed/`
  - `api/observation_universe.py`
  - `api/strategy/score_contract.py`
  - `api/strategy/common_sector_scoring_engine.py`
  - `api/strategy/indicator_plugins/`
  - `api/strategy/sector_score_aggregator.py`
  - `api/strategy/sector_allocation_pressure.py`
  - `api/strategy/macro_distribution.py`
  - `api/strategy/state_features.py`
  - `api/strategy/adaptive_offsets.py`
  - `api/strategy/regime_response_engine.py`
  - `api/strategy/allocation_offsets.py`
  - `api/backtest_judgment/`
  - `api/optimization/`
  - `config/observation_universe.yaml`
  - `config/asset_exposures.yaml`
  - `docs/SCOREFLOW_TESTBED_CURRENT_AUDIT.md`
  - `docs/SCOREFLOW_TESTBED_ARCHITECTURE.md`
  - `docs/DATA_LAYER_AND_TESTBED_SCHEMA.md`
  - `docs/SECTOR_INDICATOR_PLUGIN_SPEC.md`
  - `docs/BACKTEST_OPTIMIZATION_TESTBED_SPEC.md`
- Test commands:
  - `.venv/bin/python -m pytest tests/test_score_contract.py tests/test_data_contracts_and_testbed_schema.py tests/test_observation_universe.py tests/test_data_snapshot_service.py tests/test_common_sector_scoring_engine.py tests/test_indicator_plugin_registry.py tests/test_bottleneck_plugin.py tests/test_sector_score_aggregator.py tests/test_sector_allocation_pressure.py tests/test_macro_distribution_and_state_features.py tests/test_regime_response_engine.py tests/test_risk_budget_offsets.py tests/test_sector_tilt_pressure_integration.py tests/test_allocation_speed_friction_offsets.py tests/test_decision_logging_integration.py tests/test_realized_regime_labeler.py tests/test_judgment_backtest_evaluator.py tests/test_optimization_stores.py tests/test_candidate_generator.py tests/test_optimization_objective.py tests/test_recursive_optimizer_v1.py tests/test_robustness_tester.py tests/test_failure_analyzer.py tests/test_optimization_reporting.py tests/test_backtest_testbed_integration.py -q`
  - `.venv/bin/python -m pytest tests/test_risk_budget_engine.py tests/test_sector_tilt_engine.py tests/test_backtest_engine.py tests/test_api_backtests.py -q`
  - `.venv/bin/python -m pytest -q`
- Test result: targeted score-flow tests passed; affected existing strategy/backtest tests passed; full backend suite passed with 332 passed and 2 skipped.
- Remaining TODO / REVIEW_REQUIRED:
  - Treat optimization v1 as a deterministic testbed scaffold, not production parameter promotion.
  - Expand real data/provider integrations only through future read-only tasks.
  - Resolve pre-existing tracked deletions under `docs/DevelopLog/` and `docs/DevelopPlans/`.
- Next recommended task: Phase 4 Feature Layer hardening.

## Phase 3 Data Pipeline

- Status: complete.
- Scope: raw data pipeline only; no Feature Layer, Score Layer, investment decision, rebalancing, order candidate, broker order, or live execution behavior was added.
- Completed components:
  - Data pipeline audit and spec.
  - Data source registry in `config/data_sources.yml`.
  - Raw data DB repository for historical prices, current quotes, macro observations, data quality checks, and ingestion runs.
  - Deterministic mock market/macro providers.
  - Price history, macro, and current quote ingestion services.
  - Data quality validation for missing, stale, duplicate, non-positive, and jump warnings.
  - As-of data snapshot contract to avoid future-data leakage.
  - Idempotent backfill CLI.
  - Read-only data status API.
  - Phase 3 mock E2E closeout.
- Major files:
  - `docs/PHASE_3_DATA_PIPELINE_AUDIT.md`
  - `docs/DATA_PIPELINE_SPEC.md`
  - `docs/PHASE_3_CURRENT_PRICE_CHECK.md`
  - `docs/PHASE_3_DATA_PIPELINE_CLOSEOUT.md`
  - `config/data_sources.yml`
  - `api/data/`
  - `api/main.py`
  - `tests/test_data_source_registry.py`
  - `tests/test_raw_data_repository.py`
  - `tests/test_data_providers.py`
  - `tests/test_price_history_ingestion.py`
  - `tests/test_macro_data_ingestion.py`
  - `tests/test_current_quote_connectivity.py`
  - `tests/test_data_quality_validation.py`
  - `tests/test_data_snapshot_contract.py`
  - `tests/test_backfill_cli_idempotency.py`
  - `tests/test_data_status_api.py`
  - `tests/test_phase3_data_pipeline_e2e.py`
- Test commands:
  - `test -f docs/PHASE_3_DATA_PIPELINE_AUDIT.md && grep -E "Existing data sources|Missing pieces|current price" docs/PHASE_3_DATA_PIPELINE_AUDIT.md`
  - `test -f docs/DATA_PIPELINE_SPEC.md && grep -E "as_of_date|quality_score|future|mock provider|raw_data" docs/DATA_PIPELINE_SPEC.md`
  - `.venv/bin/python -m pytest tests/test_data_source_registry.py -q`
  - `.venv/bin/python -m pytest tests/test_raw_data_repository.py -q`
  - `.venv/bin/python -m pytest tests/test_data_providers.py -q`
  - `.venv/bin/python -m pytest tests/test_price_history_ingestion.py tests/test_macro_data_ingestion.py -q`
  - `.venv/bin/python -m pytest tests/test_current_quote_connectivity.py -q`
  - `.venv/bin/python -m api.data.check_current_quotes --provider mock`
  - `.venv/bin/python -m pytest tests/test_data_quality_validation.py -q`
  - `.venv/bin/python -m pytest tests/test_data_snapshot_contract.py -q`
  - `.venv/bin/python -m pytest tests/test_backfill_cli_idempotency.py -q`
  - `.venv/bin/python -m pytest tests/test_data_status_api.py -q`
  - `.venv/bin/python -m pytest tests/test_phase3_data_pipeline_e2e.py -q`
  - `.venv/bin/python -m pytest -q`
  - `npm --prefix web run lint`
- Test result: targeted tests passed; full backend suite passed with 304 passed and 2 skipped; web lint passed.
- Live/current price result:
  - Mock current quote check passed.
  - Live current quote check remains skipped unless `RUN_LIVE_PRICE_SMOKE=1` and read-only provider credentials are explicitly configured.
- Remaining TODO / REVIEW_REQUIRED:
  - Add real read-only historical providers only through explicit future tasks.
  - Keep Phase 4 feature computation behind the as-of snapshot contract.
  - Resolve pre-existing tracked deletions under `docs/DevelopLog/` and `docs/DevelopPlans/`.
- Next recommended task: Phase 4 Feature Layer.

## Phase Pre-3 Asset Master + Data + DB Integration

- Status: complete.
- Scope: normalized investable universe integration, read-only price provider contract, quote DB persistence, snapshots, docs, and guardrails only.
- Phase Pre-3 asset master integration added.
- Duplicate role bucket design was replaced by feature-based selectors.
- `config/universe/asset_master.yml` is the single source of truth for assets.
- `config/universe/universe_selectors.yml` resolves candidate universes by conditions.
- Resolved universe snapshots can be generated for reproducibility.
- Read-only price provider contract was added.
- Live price query smoke test was added and is gated by `RUN_LIVE_PRICE_SMOKE=1`.
- Market data DB quote storage/readback tests were added.
- End-to-end universe to live data to DB test is gated by `RUN_LIVE_PRICE_SMOKE=1` and `RUN_DB_INTEGRATION=1`.
- Live execution and broker order submission remain disabled.
- Major files:
  - `docs/ASSET_UNIVERSE_SPEC.md`
  - `docs/MARKET_DATA_DB_INTEGRATION_SPEC.md`
  - `docs/PHASE_PRE3_REPOSITORY_INSPECTION.md`
  - `config/universe/schema.yml`
  - `config/universe/asset_master.yml`
  - `config/universe/universe_selectors.yml`
  - `config/universe/snapshots/universe_snapshot_20260527.yml`
  - `api/universe/`
  - `api/market_data/`
  - `scripts/generate_universe_snapshot.py`
  - `tests/test_asset_master_loader_validator.py`
  - `tests/test_universe_selector_resolver.py`
  - `tests/test_universe_snapshot.py`
  - `tests/test_price_provider_contract.py`
  - `tests/test_market_data_db_schema.py`
  - `tests/test_market_data_db_write_read.py`
  - `tests/test_no_live_execution_guardrails.py`
  - `tests/test_asset_universe_guardrails.py`
  - `tests/integration/`
- Test commands:
  - `.venv/bin/python -m pytest tests/test_asset_master_loader_validator.py -q`
  - `.venv/bin/python -m pytest tests/test_universe_selector_resolver.py -q`
  - `.venv/bin/python -m pytest tests/test_universe_snapshot.py -q`
  - `.venv/bin/python scripts/generate_universe_snapshot.py`
  - `.venv/bin/python -m pytest tests/test_price_provider_contract.py -q`
  - `.venv/bin/python -m pytest tests/integration/test_live_price_query_smoke.py -q`
  - `.venv/bin/python -m pytest tests/test_market_data_db_schema.py -q`
  - `.venv/bin/python -m pytest tests/test_market_data_db_write_read.py -q`
  - `.venv/bin/python -m pytest tests/integration/test_universe_live_data_db_e2e.py -q`
  - `.venv/bin/python -m pytest tests/test_no_live_execution_guardrails.py tests/test_asset_universe_guardrails.py -q`
  - `.venv/bin/python - <<'PY' ... PY` documentation validation from `TASK_013_DOCUMENTATION_AND_STATUS_UPDATE.md`
  - `.venv/bin/python -m pytest -q`
- Test result: targeted tests passed; documentation validation passed; full non-live suite passed with 265 passed and 2 skipped. Live/API tests skipped by default without explicit env gates.
- Remaining TODO / REVIEW_REQUIRED:
  - Run live price smoke only when read-only provider credentials are intentionally available.
  - Run live data to DB e2e only with `RUN_LIVE_PRICE_SMOKE=1` and `RUN_DB_INTEGRATION=1`.
  - Resolve pre-existing tracked deletions under `docs/DevelopLog/` and `docs/DevelopPlans/`.
- Next recommended task: Phase 3 Build data pipeline.

## Phase 2 Account Constraint Model

- Status: complete.
- Scope: deterministic account constraint model only; no strategy, allocation, rebalancing, order candidate, broker/KIS, execution, or backtest behavior was changed.
- Major files:
  - `docs/PHASE_2_ACCOUNT_CONSTRAINT_AUDIT.md`
  - `docs/ACCOUNT_CONSTRAINT_ENGINE_SPEC.md`
  - `docs/PHASE_2_ACCOUNT_CONSTRAINT_SUMMARY.md`
  - `config/account_constraints.yaml`
  - `api/strategy/account_constraints/`
  - `tests/strategy/`
- Test commands:
  - `.venv/bin/python -m pytest tests/strategy -q`
  - `.venv/bin/python -m pytest -q`
- Test result: passed.
- Remaining TODO / REVIEW_REQUIRED:
  - Integrate the account constraint engine into future order candidate/allocation/rebalancing paths only through an explicit approved task.
  - Review account/product rule defaults before any production or execution-adjacent use.
  - Resolve pre-existing tracked deletions under `docs/DevelopLog/` and `docs/DevelopPlans/`.
- Next recommended task: Phase 3 Build data pipeline.

## Documentation / Status Consolidation Checkpoint

- Date: 2026-05-27
- Scope: documentation/status normalization only; no strategy, allocation, rebalancing, order candidate, broker/KIS, execution, or backtest behavior was changed.
- Canonical source map:
  - Master architecture/rules: `docs/MASTER_DEVELOPMENT_GUIDE.md`
  - Coding-agent operations: `AGENTS.md`
  - Global task/progress status: `DevelopPlans/STATUS.md`
  - Phase 1 detail log: `docs/PHASE_1_STATUS.md`
  - Documentation index: `docs/00_INDEX.md`
- Status normalization completed:
  - `docs/STATUS.md` is a compatibility pointer only.
  - `docs/PHASE_1_STATUS.md` is marked as Phase 1 detail only.
  - `docs/00_INDEX.md` links to canonical files and no longer duplicates stale Phase 0 TODO status.
- Untracked workflow docs:
  - Keep and track in the next documentation commit: `AGENTS.md`, `docs/MASTER_DEVELOPMENT_GUIDE.md`, `docs/00_INDEX.md`, `docs/TASK_TEMPLATE.md`, `docs/phase0/`.
  - Removed as temporary extraction artifact: `phase1_codex_tasks/`.
- Tracked deleted docs requiring approval:
  - `docs/DevelopLog/` deleted files: leave unresolved until the user chooses restore, archive, or commit deletion.
  - `docs/DevelopPlans/back_test.md`: leave unresolved until the user chooses restore, archive, or commit deletion.
  - `docs/DevelopPlans/trading-modes-development-plan.md`: leave unresolved until the user chooses restore, archive, or commit deletion.
- Generated/cache cleanup:
  - Removed safe generated/cache artifacts outside secrets/runtime data: Python `__pycache__/`, `.pytest_cache/`, root/docs `.DS_Store`, and `web/.next/`.
  - Left untouched: `API_KEY/`, `data/economic_data.db`, and `web/node_modules/`.
- Next recommended task: resolve the deleted tracked docs decision, then begin Phase 2 with a dedicated account-constraint task file before any order-candidate or execution-adjacent work.

## Notes

- Real account integration is out of scope.
- Live order execution is out of scope.
- Current development target is backtest completion, algorithm improvement, and order candidate generation only.
- Canonical status file is `DevelopPlans/STATUS.md`.
- Phase 0 task source files are currently stored under `docs/phase0/`; their `DevelopPlans/phase0/` paths are treated as logical task identifiers until the plan tree is normalized.
- Phase 0 produced:
  - `docs/PHASE_0_REPOSITORY_AUDIT.md`
  - `docs/PROJECT_GUARDRAILS.md`
  - `docs/PHASE_0_GAP_ANALYSIS.md`
  - `docs/DEVELOPMENT_SEQUENCE_BACKTEST_FIRST.md`
  - `docs/ARCHITECTURE_MAP.md`
  - `docs/PHASE_0_TEST_BASELINE.md`
- Phase 1 produced:
  - `docs/PHASE_1_STATUS.md`
  - `docs/PHASE_1_ASSET_UNIVERSE_GUARDRAILS.md`
  - `docs/PHASE_1_ASSET_UNIVERSE_AUDIT.md`
  - `config/asset_universe.yaml`
  - `config/asset_universe_mappings.yaml`
  - `config/asset_data_requirements.yaml`
  - `api/asset_universe_schema.py`
  - `api/asset_universe_loader.py`
  - `api/asset_universe_validator.py`
  - `api/asset_universe_mapping.py`
  - `api/asset_data_requirements.py`
  - `api/asset_universe_snapshot.py`
