# AI/Bio CapEx Baseline Inspection

## Scope

This note records the safe insertion points for the AI/Bio CapEx cycle batch before any runtime implementation. It is inspection-only and does not change strategy, broker, account, order, KIS, execution, allocation, rebalancing, or frontend behavior.

## Repository Context

- Repository root: `/Users/bumsangkim/Dev/TripleA`
- Python/FastAPI backend: `api/`
- Feature slice registry: `api/features/router_registry.py`
- Score pipeline extension point: `api/score_pipeline/`
- Data layer extension point: `api/data/`
- Backtest extension point: `api/score_pipeline/backtest.py` and existing top-level backtest modules
- Configuration root: `config/`
- Test root: `tests/`

## Guide Files

- `AGENTS.md`: present. Concise coding-agent guardrails.
- `README.md`: present. Architecture, layer rules, API, and test overview.
- `DevelopPlans/STATUS.md`: present. Canonical development status.
- `MASTER_DEVELOPMENT_GUIDE.md`: not present at repository root.
- `docs/MASTER_DEVELOPMENT_GUIDE.md`: not present.

Because no master development guide file exists in this checkout, this batch should treat `AGENTS.md`, `README.md`, and `DevelopPlans/STATUS.md` as the current equivalent source of project rules until a canonical master guide is restored or created in a separate documentation task.

## Required Pre-Check Paths

| Expected path | Status | Notes |
|---|---:|---|
| `api/score_pipeline/contracts.py` | present | Core score-flow dataclasses and conservative actions. |
| `api/score_pipeline/data_quality.py` | present | Raw datapoints, PIT historical snapshots, quality assessor, future-data rejection. |
| `api/score_pipeline/parameters.py` | present | YAML-backed parameter registry with conservative fallback. |
| `api/score_pipeline/backtest.py` | present | Pipeline backtest config, runner, clock, and metrics. |
| `api/features/router_registry.py` | present | Imports and includes feature routers through `include_feature_routers(app)`. |
| `tests/architecture/` | present | Import and feature-slice boundary tests exist. |
| `pytest.ini` | present | Test path is `tests`; `pythonpath = .`; integration/live/db markers are declared. |

## Existing Insertion Points

- Score/plugin contracts can be extended under `api/score_pipeline/` without touching `api/strategy/**`.
- Read-only feature APIs should use the existing vertical-slice pattern under `api/features/<feature>/`.
- New feature routers should be registered in `api/features/router_registry.py` only when a task explicitly requires router integration.
- Raw data and PIT snapshot behavior should use or extend `api/data/` and existing score pipeline data-quality contracts.
- Backtest-only validation should remain non-executable and avoid broker/order paths.
- Config-driven parameters should be placed under `config/` or `config/parameters/`, not hardcoded in source.

## Router Registry

`api/features/router_registry.py` defines `include_feature_routers(app: FastAPI)`. It imports router modules inside the function and calls `app.include_router(...)` for each feature. This supports adding a read-only CapEx feature router later with a narrow registry edit, if a task explicitly permits it.

## Architecture Boundary Tests

Existing architecture tests include:

- `tests/architecture/test_import_contracts.py`
- `tests/architecture/test_feature_contracts.py`

They check feature-router, feature-service, repository, and domain import boundaries. Current tests intentionally collect some legacy dependency information without failing.

## Test Command Convention

Use the repository virtual environment when available:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --collect-only -q
```

The task pack references `pytest`; using `.venv/bin/python -m pytest` is the equivalent command for this checkout.

## Working Tree Before Task 001

The working tree was not clean before this task started. Existing changes were not created by this task and are treated as unrelated unless later task scopes explicitly allow them.

```text
 M api/brokers/kis/config.py
 M api/core/dependencies.py
 M config/indicators.yaml
 M scripts/collect_historical_data.py
 M scripts/send_daily_macro_report.py
 M web/components/layout/Header.tsx
?? api/services/
```

Notable risk: `api/brokers/kis/config.py` and `web/components/layout/Header.tsx` are modified before this batch and are forbidden for Task 001. They must not be staged or changed by this task.

## Paths To Keep Untouched In This Batch Unless Explicitly Allowed

- `api/brokers/**`
- `api/features/orders/**`
- `api/strategy/**`
- `web/**`
- `.env*`
- local DB files such as `*.db` and `*.sqlite*`
- caches and generated files such as `__pycache__/`, `.pytest_cache/`, `.next/`, and `node_modules/`

## Baseline Conclusion

The repository has the required FastAPI-style backend, score pipeline, data layer, feature router registry, config root, tests, and architecture boundary tests needed for a read-only AI/Bio CapEx extension. The current integration does not require live execution path edits.

Proceed conservatively: add independent contracts, configs, read-only adapters, feature/report APIs, and tests only in the task-approved files. Missing business rules should remain `REVIEW_REQUIRED`, `NO_ACTION`, `HOLD`, or equivalent documentation rather than being invented.
