# Score Pipeline Architecture Status

## Completed Tasks

- TASK 000: repository and architecture audit.
- TASK 001: pipeline contracts and serializable types.
- TASK 002: configuration and parameter registry.
- TASK 003: data snapshot and quality layer.
- TASK 004: feature plugin layer.
- TASK 005: score layer core.
- TASK 006: macro regime distribution engine.
- TASK 007: sector scoring engine.
- TASK 008: risk budget and hard constraint gate.
- TASK 009: allocation and rebalancing engine.
- TASK 010: backtest integration and leakage tests.
- TASK 011: reporting, audit, and review-only order candidates.

## Changed Files

- `api/score_pipeline/`
- `config/parameters/default.yaml`
- `config/parameters/sectors.yaml`
- `docs/SCORE_PIPELINE_ARCHITECTURE_AUDIT.md`
- `docs/SCORE_PIPELINE_STATUS.md`
- `docs/codex_tasks/score_pipeline/`
- `tests/test_score_pipeline_*.py`

## Tests Run

- `.venv/bin/python -m pytest -q tests/test_score_pipeline_contracts_parameters.py`
- `.venv/bin/python -m pytest -q tests/test_score_pipeline_contracts_parameters.py tests/test_score_pipeline_data_feature_score.py`
- `.venv/bin/python -m pytest -q tests/test_score_pipeline_engines.py`
- `.venv/bin/python -m pytest -q tests/test_score_pipeline_backtest_audit_order.py`
- `.venv/bin/python -m pytest -q tests/test_score_pipeline_contracts_parameters.py tests/test_score_pipeline_data_feature_score.py tests/test_score_pipeline_engines.py tests/test_score_pipeline_backtest_audit_order.py` — 28 passed.
- `.venv/bin/python -m pytest -q tests/test_score_pipeline_contracts_parameters.py tests/test_score_pipeline_data_feature_score.py tests/test_score_pipeline_engines.py tests/test_score_pipeline_backtest_audit_order.py tests/test_regime_response_engine.py tests/test_risk_budget_engine.py tests/test_backtest_engine.py tests/test_no_live_execution_guardrails.py` — 35 passed.
- `.venv/bin/python -m pytest -q` — 515 passed, 2 skipped.
- `npm run lint` — passed.
- `npm run build` — passed.
- `npm test -- --runInBand` — not available, `web/package.json` has no `test` script.

## Final Verification

- `git diff --check` passed.
- Safety scan found no prohibited implementation pattern in `api/score_pipeline`; prohibited names appear only in audit/task text and a test assertion checking no broker payload exists.
- Staging excludes `.env`, `API_KEY/`, DB files, caches, `web/.next/`, `web/node_modules/`, and `data/`.

## Naming Normalization

- Renamed the temporary architecture package to `api/score_pipeline`.
- Renamed matching tests, docs, task-pack paths, parameter versions, and model version values to the `score_pipeline_*` naming scheme.
- Reviewed external-contract candidates and did not rename DB columns, API fields, serialized audit field names, `current_*` state fields, `latest_*` lookup names, order-draft identifiers, or domain asset classes such as `real_asset` and `fixed_income`.
- Internal helper/local names with development-history wording were normalized without changing formulas or strategy behavior.

## Known Limitations

- Score pipeline is implemented as an independent architecture layer and is not yet wired into production FastAPI endpoints.
- Tax impact remains a hook/config assumption, not a production tax model.
- Backtest integration is a smoke-level pipeline adapter with leakage guards, not a replacement for all dashboard backtest flows.
- Order candidates are user-review-only and non-executable.

## Deferred Items

- UI/API exposure for score pipeline runs.
- Persistent storage for score pipeline decision logs.
- Production-grade tax model.
- User-approved execution workflow.

## Safety Status

- No live execution added.
- No automatic execution added.
- No broker order call added.
- `execution_allowed` defaults to `false`.
- Hard constraints block actions.
- Poor data quality falls back conservatively.
- Commit/push pending final git staging.
