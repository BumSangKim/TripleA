# New Pipeline Architecture Status

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

- `api/new_pipeline/`
- `config/parameters/default.yaml`
- `config/parameters/sectors.yaml`
- `docs/NEW_PIPELINE_ARCHITECTURE_AUDIT.md`
- `docs/NEW_PIPELINE_STATUS.md`
- `docs/codex_tasks/new_pipeline/`
- `tests/test_new_pipeline_*.py`

## Tests Run

- `.venv/bin/python -m pytest -q tests/test_new_pipeline_contracts_parameters.py`
- `.venv/bin/python -m pytest -q tests/test_new_pipeline_contracts_parameters.py tests/test_new_pipeline_data_feature_score.py`
- `.venv/bin/python -m pytest -q tests/test_new_pipeline_engines.py`
- `.venv/bin/python -m pytest -q tests/test_new_pipeline_backtest_audit_order.py`
- `.venv/bin/python -m pytest -q tests/test_new_pipeline_contracts_parameters.py tests/test_new_pipeline_data_feature_score.py tests/test_new_pipeline_engines.py tests/test_new_pipeline_backtest_audit_order.py` — 28 passed.
- `.venv/bin/python -m pytest -q` — 515 passed, 2 skipped.
- `npm run lint` — passed.
- `npm run build` — passed.
- `npm test -- --runInBand` — not available, `web/package.json` has no `test` script.

## Final Verification

- `git diff --check` passed.
- Safety scan found no prohibited implementation pattern in `api/new_pipeline`; prohibited names appear only in audit/task text and a test assertion checking no broker payload exists.
- Staging excludes `.env`, `API_KEY/`, DB files, caches, `web/.next/`, `web/node_modules/`, and `data/`.

## Known Limitations

- New pipeline is implemented as an independent architecture layer and is not yet wired into production FastAPI endpoints.
- Tax impact remains a hook/config assumption, not a production tax model.
- Backtest integration is a smoke-level pipeline adapter with leakage guards, not a replacement for all dashboard backtest flows.
- Order candidates are user-review-only and non-executable.

## Deferred Items

- UI/API exposure for new pipeline runs.
- Persistent storage for new pipeline decision logs.
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
