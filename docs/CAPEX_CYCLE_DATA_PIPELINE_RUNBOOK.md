# CapEx Cycle Data Pipeline Runbook

## Scope

This runbook documents the read-only AI/Bio CapEx data path from source configuration through ingestion, point-in-time snapshots, feature materialization, score/report output, and verification.

It is operational documentation only. It does not define new strategy rules and does not enable live orders, automatic execution, account mutation, broker order submission, or order candidate generation.

## Source Of Truth

- Source catalog: `config/data_sources/capex_cycle_sources.yaml`
- Raw data contracts: `api/data/capex_models.py`
- Fetch job contracts: `api/data/capex_jobs.py`
- Read-only adapter ports: `api/data/capex_ports.py`
- Ingestion service: `api/data/capex_ingestion_service.py`
- Raw repository: `api/data/capex_repository.py`
- PIT snapshot builder: `api/data/capex_snapshot_builder.py`
- Feature materializer: `api/data/capex_feature_materializer.py`
- Source health view: `api/features/capex_cycle/source_health.py`
- Research report service: `api/features/capex_cycle/report_service.py`
- Research report endpoint: `GET /api/capex-cycle/report`

## Pipeline Flow

1. The source catalog defines canonical metrics, source priority, cadence, stale windows, release lag expectations, units, and PIT availability rules.
2. Read-only adapters parse provider responses into raw metric points and fetch logs. Tests use fixtures; live calls require explicit adapter wiring and credentials outside source control.
3. `CapexIngestionService.run_fetch_job` executes an explicit `CapexFetchJobRequest`. Requests default to dry-run behavior.
4. The raw repository stores idempotent metric rows, fetch logs, and data quality issues in a caller-provided database connection.
5. `CapexSnapshotBuilder` constructs decision-time snapshots and excludes rows whose `available_at` is after the requested decision time.
6. `CapexFeatureMaterializer` maps canonical raw metrics into plugin input objects while preserving warnings and reason metadata.
7. Score, scenario, and valuation components produce read-only research outputs with reasons, warnings, confidence, and version metadata.
8. The report service and `GET /api/capex-cycle/report` endpoint aggregate results for research review only.

## Source Groups

The current catalog defines these source groups:

- `fred_alfred`: read-only macro, rates, FX, and revision-aware FRED/ALFRED series. Live use should provide a FRED API key through environment or runtime configuration; fixture tests do not require credentials.
- `sec_edgar_companyfacts`: read-only SEC company facts and segment disclosures. Live use should provide a compliant user agent through runtime configuration; fixture tests do not require network access.
- `opendart`: read-only Korean company filing data. Live use should provide an OpenDART API key through runtime configuration; fixture tests do not require credentials.
- `ecos`: read-only Bank of Korea macro, rates, FX, and trade series. Live use should provide an ECOS API key through runtime configuration; fixture tests do not require credentials.
- `kis_readonly`: read-only quotation and fundamental lookup boundary only. It must remain separate from broker account, balance, order, or execution paths.
- `optional_licensed_vendor`: disabled placeholder for licensed CapEx, backlog, and industry datasets. It is optional and must not be scraped or used without a valid license and explicit integration task.

## Credentials Policy

- Do not commit credentials, account passwords, tokens, local databases, or `.env` files.
- Adapter tests use local fixtures and injected clients or transports.
- Live price or provider queries, if enabled by a later task, must be read-only and explicitly gated by environment variables.
- KIS usage in this slice is limited to read-only quote or fundamental data. It must not require order permission and must not call account, balance, order, or execution endpoints.
- Optional licensed vendor integration remains disabled until an explicit licensed-data task defines a compliant adapter.

## Cadence, Stale, And PIT Policy

Cadence and stale thresholds are data, not hardcoded source constants. The catalog records each metric's cadence, `stale_after_days`, `expected_release_lag_days`, unit, and PIT availability rule.

Operational interpretation:

- Daily market and FX inputs should be reviewed quickly when stale.
- Quarterly filing-derived inputs may remain valid across reporting windows but must be checked against the catalog stale threshold.
- Rows with `available_at` after `decision_time` are not eligible for a PIT snapshot.
- Restatements or revised data are usable only when their own availability timestamp is at or before the decision time.
- Unit mismatches, missing metadata, or unknown source priority should produce warnings and review states instead of inferred investment actions.

## Rate Limit And Scheduling Policy

There is no automatic scheduler or background ingestion loop in this slice. Ingestion is manual and request-driven.

Future live or provider-backed ingestion should:

- start with dry-run requests;
- respect provider rate limits and terms;
- record fetch logs and data quality issues;
- avoid retry loops that could behave like an unattended production feed;
- keep source health visible before any downstream interpretation.

## Manual Ingestion And Dry Run

No CapEx-specific CLI exists in this implementation. Use the service contract or the focused tests as the documented operational path.

Dry-run behavior is represented by `CapexFetchJobRequest(dry_run=True)`. Dry-run fetches data and records a result object but does not persist raw metric rows.

Normal persistence requires an explicit `CapexFetchJobRequest(dry_run=False)` and a caller-provided repository or test database connection. This still remains read-only from a trading and broker perspective.

Useful service verification:

```bash
.venv/bin/python -m pytest tests/data/test_capex_ingestion_service.py -q
```

## Source Health Interpretation

Source health is a research audit view, not an execution gate. It summarizes fetch logs, data quality issues, catalog enablement, and freshness.

Expected statuses:

- `OK`: source has usable recent data.
- `STALE`: source exists but freshness is outside the catalog stale policy.
- `PARTIAL`: source has data with quality warnings or incomplete coverage.
- `MISSING`: expected source data is absent.
- `DISABLED`: catalog marks the source as unavailable by default.
- `FIXTURE_ONLY`: data is suitable for local test verification only.

Poor or unknown health should lead to conservative review states such as `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY`. It must not be converted into an automatic trade action.

## Conservative Fallbacks

The CapEx data path uses conservative behavior on uncertainty:

- Unknown provider route: fail the fetch job with an audit reason.
- Missing source data: keep output partial or unavailable and emit `REVIEW_REQUIRED`.
- Future data: exclude it from PIT snapshots.
- Unit mismatch: keep the affected feature unavailable and emit a warning.
- Missing valuation inputs: leave fair value fields as `None`.
- Low source health: lower confidence or mark review required; do not infer a trade.
- Optional licensed vendor data unavailable: continue with documented source priority and warnings.

Allowed review states remain `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, and `RISK_REDUCE_ONLY`.

## Verification Commands

Adapter and contract checks:

```bash
.venv/bin/python -m pytest tests/data/adapters/test_fred_alfred_adapter.py -q
.venv/bin/python -m pytest tests/data/adapters/test_sec_companyfacts_adapter.py -q
.venv/bin/python -m pytest tests/data/adapters/test_opendart_adapter.py -q
.venv/bin/python -m pytest tests/data/adapters/test_ecos_adapter.py -q
.venv/bin/python -m pytest tests/data/adapters/test_kis_readonly_adapter.py -q
.venv/bin/python -m pytest tests/data/adapters/test_vendor_optional_contracts.py -q
```

Repository, ingestion, PIT, and materialization checks:

```bash
.venv/bin/python -m pytest tests/data/test_capex_raw_repository.py -q
.venv/bin/python -m pytest tests/data/test_capex_ingestion_service.py -q
.venv/bin/python -m pytest tests/data/test_capex_snapshot_builder.py -q
.venv/bin/python -m pytest tests/data/test_capex_feature_materializer.py -q
```

Report and health checks:

```bash
.venv/bin/python -m pytest tests/features/capex_cycle/test_report_service.py -q
.venv/bin/python -m pytest tests/features/capex_cycle/test_report_router.py -q
.venv/bin/python -m pytest tests/features/capex_cycle/test_source_health.py -q
```

End-to-end fixture validation:

```bash
.venv/bin/python -m pytest tests/integration/test_capex_etl_to_report_smoke.py -q
```

The integration smoke test validates fixture source rows through adapter-like fetch output, raw repository persistence, PIT snapshot filtering, feature materialization, score/scenario/valuation composition, source health, and report/API-shaped output.

## Out Of Scope

The following remain out of scope for this data pipeline:

- live orders;
- automatic execution;
- order candidate generation;
- broker account mutation;
- KIS account, balance, order, or execution endpoints;
- licensed-vendor scraping;
- automatic parameter promotion;
- standalone return optimization.

Any future change that touches those areas requires a separate task, tests, and explicit approval.

