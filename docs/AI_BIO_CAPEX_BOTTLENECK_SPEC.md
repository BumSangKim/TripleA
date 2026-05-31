# AI/Bio CapEx Bottleneck Implementation Spec

## Purpose

This document is the canonical implementation spec for the AI/Bio CapEx cycle batch. It defines a read-only, score-flow extension for evaluating AI infrastructure CapEx cycles and Bio/Pharma CapEx bottleneck infrastructure without adding live execution, automatic order generation, or clinical event betting.

The spec is based on the repository baseline in `docs/AI_BIO_CAPEX_BASELINE_INSPECTION.md`. `MASTER_DEVELOPMENT_GUIDE.md`, `deep-research-report.md`, and `작업 파일 생성 규칙.txt` were not present in this checkout, so `AGENTS.md`, `README.md`, and `DevelopPlans/STATUS.md` remain the active project-rule references for this batch.

## Investment Premise

The target opportunity is not short-term clinical event prediction. The Bio/Pharma side should evaluate infrastructure and service bottlenecks created by durable biopharma CapEx, such as manufacturing capacity, tooling, testing, cold-chain or lab infrastructure, and other measurable buildout constraints.

The AI side should evaluate infrastructure cycle conditions around AI buildout demand and supplier constraints. Outputs remain research scores, scenario distributions, valuation context, and audit explanations. They must not become direct buy/sell/order triggers.

## Non-Negotiable Boundaries

- No Threshold Switch: avoid binary buy/sell threshold switches.
- Use continuous Score Flow: produce continuous bounded scores and confidence metadata.
- Hard Constraints First: account, eligibility, risk, and execution constraints stay hard constraints outside this layer.
- Backtest Before Execution: this layer can support backtest smoke tests only.
- Explain Every Decision: outputs require reason codes, warnings, source references, and fallback notes.
- Conservative Fallback on Uncertainty: use only `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY`.
- No Default Automatic Execution: no broker order submission, no automatic real orders, and no order candidates in this batch.
- Parameters are data: strategy parameters must live in config or parameter registries, not hardcoded source constants.

## Architecture Insertion Points

Later tasks may add code only through explicit task-approved extension points:

- Score pipeline contracts and pure plugins under `api/score_pipeline/`.
- Read-only feature slice under `api/features/capex_cycle/`.
- Data adapter ports and read-only adapters under `api/data/` or a task-approved equivalent.
- Config and parameter YAML files under `config/` and `config/parameters/`.
- PIT snapshot, audit, and raw repository layers under task-approved data/persistence modules.
- Backtest smoke and future-data leakage tests under `tests/`.
- Read-only report and source-health outputs under a task-approved feature API.

The following areas are not extension points for this batch unless a later task explicitly allows a narrow backward-compatible edit:

- `api/brokers/**`
- `api/features/orders/**`
- `api/strategy/**`
- `web/**`
- `.env*`
- local DB or runtime artifacts

## Scoring Formula

The canonical final score formula for the Bio/Pharma CapEx Bottleneck layer is:

```text
Final = 0.40*StructuralMoat
      + 0.35*DemandMomentum
      + 0.25*FinancialQuality
      - 0.35*RiskPenalty
```

Formula notes:

- Component scores must be continuous and bounded by the contracts defined in later tasks.
- Component weights are configuration data and should be loaded from approved config files.
- Missing or unreliable inputs must lower confidence and add warnings rather than silently fabricating values.
- The formula is research scoring only. It does not override account constraints, risk limits, or execution controls.

## AI CapEx Cycle Inputs

AI CapEx inputs should be measurable, auditable, and point-in-time safe. Examples include:

- Hyperscaler CapEx trend proxies.
- AI accelerator, data-center, power, networking, cooling, and memory supply indicators.
- Demand-side backlog or utilization proxies where available.
- Data-quality and stale-data metadata for each source.

Unclear source mappings must be marked `REVIEW_REQUIRED` instead of filled with aggressive assumptions.

## Bio/Pharma CapEx Bottleneck Inputs

Bio/Pharma inputs should focus on bottleneck infrastructure rather than clinical trial outcomes. Examples include:

- Capacity expansion and manufacturing infrastructure metrics.
- CDMO, life-science tooling, lab automation, testing, or cold-chain infrastructure indicators.
- Financial-quality inputs such as margin quality, leverage, cash-flow durability, and reinvestment capacity.
- Risk inputs such as concentration, regulatory exposure, financing stress, or source quality issues.

Clinical milestone, trial readout, approval, or binary event data may be recorded as contextual risk/audit information only. It must not be used as a direct buy/sell switch.

## Fallback Policy

Only these conservative fallback states are allowed:

- `NO_ACTION`
- `HOLD`
- `REVIEW_REQUIRED`
- `RISK_REDUCE_ONLY`

Fallback triggers include missing source metadata, stale data, source disagreement, unavailable PIT timestamp, invalid parameter version, unknown universe mapping, insufficient valuation data, or any condition that would require live account or execution state.

## Output Contract Expectations

Outputs should support read-only research and audit workflows:

- Feature values and raw snapshots with `as_of_date` and `available_at`.
- Score outputs with component details, confidence, reason codes, warnings, and parameter versions.
- Scenario distributions with conservative handling for missing inputs.
- Valuation/fair-value context that is not a standalone order signal.
- Report/API outputs that explain input lineage from source fixture or adapter through raw repository, PIT snapshot, feature materializer, score/scenario/valuation, and final report.

## Explicitly Out Of Scope

- Live broker execution.
- KIS or other broker order submission.
- Automatic real-order generation.
- Order candidate creation.
- Direct clinical trial success prediction.
- Clinical event scoring as a buy/sell trigger.
- Threshold buy/sell switches.
- Account-specific behavior or eligibility decisions unless a task explicitly adds read-only reporting metadata.
- Frontend dashboard work, including optional task `900_optional_frontend_readonly_dashboard.md`.

## Staged Task Map

Foundation:

- `001_inspect_current_structure`
- `002_write_bio_capex_spec_doc`

Contracts, config, scoring, and pure plugins:

- `003_add_capex_contract_types`
- `004_add_ai_capex_parameter_config`
- `005_add_bio_capex_parameter_config`
- `006_add_score_definitions_ai_config`
- `007_add_capex_bottleneck_universe_config`
- `008_add_capex_common_scoring_utils`
- `009_implement_ai_capex_cycle_plugin`
- `010_implement_bio_capex_bottleneck_plugin`
- `011_implement_capex_scenario_engine`
- `012_implement_valuation_engine`

Read-only feature API and audit:

- `013_add_data_adapter_ports`
- `014_add_fixture_pit_adapter`
- `015_add_capex_cycle_feature_schemas`
- `016_add_capex_cycle_feature_ports`
- `017_add_capex_cycle_feature_service`
- `018_add_capex_cycle_feature_router`
- `019_register_capex_cycle_feature_router`
- `020_add_snapshot_audit_models`
- `021_add_snapshot_audit_repository`
- `022_add_capex_backtest_smoke`
- `023_add_capex_future_leakage_test`
- `024_add_architecture_boundary_tests`
- `025_update_runbook_and_final_verification`

Data pipeline and input-to-output validation:

- `026_add_data_source_catalog_config`
- `027_add_canonical_raw_data_models`
- `028_add_raw_data_repository_ports`
- `029_add_fetch_job_contracts`
- `030_add_raw_data_migrations`
- `031_implement_fred_alfred_adapter`
- `032_implement_sec_companyfacts_adapter`
- `033_implement_opendart_adapter`
- `034_implement_ecos_adapter`
- `035_implement_kis_readonly_market_adapter`
- `036_add_optional_vendor_adapter_contracts`
- `037_add_raw_repository_implementation`
- `038_implement_ingestion_orchestrator`
- `039_add_snapshot_builder_from_raw`
- `040_add_capex_feature_materializer`
- `041_add_capex_report_output_contracts`
- `042_add_capex_report_service`
- `043_add_capex_report_router`
- `044_add_source_health_api`
- `045_add_etl_e2e_smoke_test`
- `046_update_data_pipeline_runbook`

## Acceptance Notes For Later Tasks

Each non-documentation task must add or update tests. Across the batch, tests must prove the full read-only path:

```text
source fixture
-> adapter parse
-> raw repository
-> PIT snapshot
-> feature materializer
-> score/scenario/valuation
-> report/API output
```

If a later task uncovers a rule mismatch, missing source, or account/execution dependency, the correct behavior is to stop that task or return a conservative fallback state. Do not invent missing investment rules.
