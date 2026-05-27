# Phase 0 Test Baseline

## 1. Test Environment

- Date: 2026-05-26
- OS/environment: macOS Darwin 25.5.0 arm64 (`Bumsangui-MacBookAir.local`)
- Language/runtime version: Python 3.14.2
- Package manager: `pip` with `requirements.txt`; `npm` exists for `web/`
- Test framework: pytest 9.0.3
- Dependency installation command used: Not run during this task; existing `.venv` was used.

## 2. Test Discovery

| Source | Finding |
|---|---|
| Test directory | `tests/` contains 24 Python test files matching `test_*.py`. |
| Test config | `pytest.ini` sets `testpaths = tests` and `pythonpath = .`. |
| CI config | No `.github/`, CI workflow, `tox.ini`, or equivalent CI config was found within the inspected depth. |
| Makefile/script | No `Makefile` was found. `README.md` documents `PYTHONPATH=. python -m pytest`; `web/package.json` has `lint` and `build`, but no `test` script. |
| Frontend checks | `web/package.json` provides `npm run lint` and `npm run build`; these are not the primary test command for this Python baseline. |

## 3. Test Command Used

```bash
.venv/bin/python -m pytest
```

## 4. Result

Passed.

Summary:

```text
collected 142 items
142 passed in 2.88s
```

## 5. Failure Summary

No failures.

| Test/Command | Failure Summary | Likely Cause | Related to This Task? |
|---|---|---|---|
| `.venv/bin/python -m pytest` | None | Not applicable | No |

## 6. Missing Test Areas

| Area | Test Exists? | Notes |
|---|---:|---|
| Data cleaning | Partial | Collector/service tests exist for macro, market, trade, and KIS parsing, but a distinct raw-data cleaning contract is not yet visible. |
| Feature calculation | Partial | Some derived values are tested through services and engines; no dedicated feature layer tests because no explicit feature layer exists yet. |
| Score calculation | Partial | Macro, bottleneck sector, sector tilt, risk budget, and allocator tests exist; standard score contract tests are missing. |
| Regime distribution calculation | No | Current macro engine tests cover score/label behavior, not regime distributions. |
| Sector scoring | Yes | `tests/test_bottleneck_sector_engine.py` and `tests/test_sector_tilt_engine.py` exist. |
| Risk budget calculation | Yes | `tests/test_risk_budget_engine.py` exists. |
| Target allocation calculation | Partial | `tests/test_triplea_allocator.py` and API engine/rebalancing tests exist, but target range behavior is not yet a separate contract. |
| Rebalancing score calculation | No | Rebalancing suggestions/results are tested, but no rebalancing intensity score exists yet. |
| Account constraint validation | Partial | Mode policy, account policy, and order boundary tests exist; no dedicated account constraint engine tests. |
| Order candidate generation | Yes | `tests/test_api_orders.py` covers draft and approval boundaries. |
| Backtest simulation | Yes | `tests/test_backtest_engine.py`, `tests/test_api_backtests.py`, and request contract tests exist. |
| Future-data leakage prevention | Partial | On-or-before market data behavior is covered indirectly; release-calendar/revised-data leakage tests are missing. |
| Parameter loading and versioning | Partial | Config metadata and strategy metadata tests exist; parameter approval/version metadata tests are missing. |
| Conservative fallback behavior | Partial | Mode rejection, KIS error handling, and some missing-data cases are tested; standard fallback outputs are not yet consistently modeled. |

## 7. Recommended Next Test Work

- Add asset universe schema tests in Phase 1.
- Add account constraint engine tests before expanding order-candidate behavior.
- Add data quality and release-date tests for macro, market, trade, and bottleneck data.
- Add feature layer contract tests once explicit feature models exist.
- Add standard score output contract tests covering confidence, data quality, stability, reason codes, parameter version, and model version.
- Add macro regime distribution tests before replacing label-based behavior.
- Add backtest leakage tests for release lag, revised macro data, survivorship bias, and future price/constituent protection.
- Add rebalancing intensity tests before using deviations as order-candidate drivers.
- Add audit log completeness tests for score inputs, constraints, warnings, and versions.

## 8. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q005-001 | Should frontend `npm run lint` and `npm run build` be part of the required baseline, or only backend pytest? | Defines future CI and task acceptance expectations. | Treat pytest as current baseline; add frontend checks in a dedicated UI/CI task. |
| Q005-002 | Should external data collection tests run with network disabled by default? | Prevents flaky tests and accidental dependence on live services. | Use mocks/fixtures by default. |
| Q005-003 | What minimum coverage is required before strategy promotion? | Ensures future strategy changes are backed by tests and backtests. | `REVIEW_REQUIRED` before promotion. |
| Q005-004 | Should `DevelopPlans/STATUS.md` include test command history for every task or only the latest task? | Affects how future agents audit task progress. | Record the latest task command and result; keep detailed evidence in task documents. |

