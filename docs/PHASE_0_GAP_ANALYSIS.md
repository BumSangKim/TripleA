# Phase 0 Gap Analysis Against MASTER_DEVELOPMENT_GUIDE

## 1. Summary

Current readiness: Partially ready.

The repository already has a FastAPI dashboard, mode separation, a backtest engine, strategy modules, order-candidate logging, and tests. It is ready for continued documentation and backtest-first cleanup, but it is not yet ready for production strategy promotion or real account execution.

The most important gaps are the absence of a full account constraint engine, hardcoded threshold/regime behavior in strategy modules, incomplete score-output metadata, and unresolved data leakage/reproducibility rules for historical macro and market data.

## 2. Critical Safety Gaps

- Live broker order submission is not observed, and live order approval is rejected; this is a positive safety state that must be preserved.
- Order draft generation exists before a complete account/legal/product constraint layer exists. Future work must add hard constraint filtering before expanding order-candidate behavior.
- Macro allocation currently depends on regime labels and fixed bucket shifts, which conflicts with the target regime-distribution and gradual score-flow model.
- Several strategy parameters are configurable in YAML, but important thresholds, score weights, and tilt defaults remain hardcoded in Python.
- Backtest data access uses as-of lookup helpers, but release lag, revised macro data, survivorship bias, and automatic data collection reproducibility are not fully specified.
- Standard score metadata is incomplete across strategy outputs; confidence, data quality, stability, parameter version, and model version are not consistently present.
- Conservative fallback behavior is documented in policy, but not yet consistently represented as typed decision outputs across strategy and execution-adjacent modules.

## 3. Gap Table

| Area | Current State | Required State | Gap | Risk | Recommended Phase |
|---|---|---|---|---|---|
| Asset Universe | `config/investment_universe.yaml`, `config/backtest_assets.yaml`, and DB seeding exist. | Config-driven universe with schema checks, active flags, source metadata, and reviewable defaults. | Universe exists but schema/version/approval metadata is limited. | Medium: accidental asset inclusion or unclear asset role. | Phase 1 |
| Account Constraints | Account policies and mode policies exist; no dedicated constraint engine observed. | Explicit account model enforcing account/legal/product/cash/min-order constraints before candidates. | Constraints are partial and spread across policy tables, services, and modes. | High: unsafe candidates if future execution expands. | Phase 2 |
| Data Pipeline | SQLite tables, collectors, and services exist for market, macro, trade, bottleneck, account, and backtest data. | Raw/feature/score/decision separation with versioning and quality metadata. | Data layers are mixed; raw versus derived ownership is not consistently explicit. | Medium: reproducibility and data lineage risk. | Phase 3 |
| Feature Layer | Some service functions calculate histories/snapshots; no clear feature contract observed. | Normalized feature outputs with dates, sources, release timing, and quality metadata. | Feature generation is implicit inside services/engines. | High: future-data and inconsistent normalization risk. | Phase 4 |
| Score Layer | Macro, sector, risk, and allocation modules produce scores or score-like outputs. | Comparable score outputs with confidence, data quality, stability, reason codes, versions. | Score contract is incomplete and not centralized. | High: hard-to-audit decisions. | Phase 5 |
| Backtest Engine | `api/backtest_engine.py` simulates rebalances and persists metrics/trades/decisions. | Leakage-safe backtest with reproducible data, release calendars, turnover/cost/tax treatment, and test coverage. | Engine exists, but release-lag/revision/survivorship policy is not complete. | High: misleading validation results. | Phase 6 |
| Macro Regime Engine | `api/strategy/macro_engine.py` produces score plus dominant label using thresholds. | Regime score distribution consumed continuously by allocation. | No distribution output; threshold label can drive fixed shifts. | High: violates score-flow principle. | Phase 7 |
| Sector Scoring | Bottleneck sector scoring blends components and reasons. | Decomposable sector/asset scores with risk, confidence, data quality, and version metadata. | Component scoring exists but hardcoded weights/cutoffs and incomplete metadata remain. | Medium: opaque or brittle sector tilts. | Phase 8 |
| Risk Budget | `RiskBudgetEngine` clamps bucket min/max and preserves bucket proportions. | Portfolio and account-level risk budgets with constraints, confidence, and explainability. | Portfolio bucket logic exists; account-level risk budget is missing. | High: account-specific risk breach risk. | Phase 9 |
| Allocation | `TripleAAllocator` combines macro, sector tilt, and risk budget into weights. | Target ranges, gradual changes, turnover/cost/tax awareness, and full score-flow inputs. | Uses fixed macro shifts and label-based tilts; target ranges are limited. | High: abrupt or insufficiently explained allocation changes. | Phase 10 |
| Rebalancing | Current services compute target deviations and suggestions; results are persisted. | Rebalancing intensity score with costs, taxes, cash, constraints, and reviewable candidates. | Threshold deviation logic exists; intensity score and full constraint/cost checks are incomplete. | Medium: overtrading or weak candidate rationale. | Phase 11 |
| Reporting/Audit | Reasons, logs, backtest decisions, alerts, and order logs exist. | Decision logs with versions, warnings, data quality, parameter IDs, and full traceability. | Audit records exist but are not complete master-guide contracts. | Medium: hard to explain or reproduce decisions. | Phase 12 |
| Order Candidates | Draft generation from rebalancing deviations exists; paper approval is log-only. | Constraint-filtered candidates with account/product/order safety validation and user review. | Candidate generation precedes complete hard constraint layer. | High: candidate quality and future execution safety risk. | Phase 13 |
| Execution | KIS balance sync is read-only; live approval is rejected; no order placement observed. | User-approved only after all prior phases; automatic execution only as optional future capability. | Safe current state, but naming `/execute` may confuse log-only behavior. | Medium: operational misunderstanding. | Later |

## 4. Prohibited Pattern Check

| Prohibited Pattern | Found? | Location | Required Follow-Up |
|---|---:|---|---|
| Hardcoded strategy parameters | Yes | `api/strategy/macro_engine.py`, `api/strategy/sector_tilt_engine.py`, `_macro_adjusted_profile` in `api/strategy/triplea_allocator.py` | Move approved parameters into versioned configuration in later phases. |
| Single-threshold regime switching | Yes | `api/strategy/macro_engine.py::_regime_from_score` and indicator thresholds | Replace with regime distribution and continuous score flow. |
| Boolean-driven buy/sell logic | Partial | `api/services.py::create_order_draft` maps deviation sign to BUY/SELL candidates | Add rebalancing intensity and hard constraint filtering before expanding candidates. |
| Live strategy logic without backtesting | No direct live execution found | Live KIS sync is read-only; backtests exist | Preserve live read-only mode until safety phases are complete. |
| Future-data leakage risk | Yes | Backtest data assumptions and automatic collection path | Define release calendars, revised-data handling, and reproducible snapshots. |
| Ignoring account constraints | Partial | Allocation path lacks dedicated account constraint engine | Build account constraint model before candidate expansion. |
| Signals without data quality checks | Yes | Strategy outputs do not consistently include quality/confidence metadata | Add standard score contract and conservative fallback behavior. |
| Unexplained buy/sell decisions | Partial | Order candidates include reasons, but not full score/constraint trace | Expand reporting/audit and candidate rationale. |
| Mapping raw data directly to orders | No direct raw-data-to-order path found | Current order candidates come from target deviations | Keep separation and add hard constraint filter. |
| Default automatic order execution | No | `api/kis.py` read-only; `approve_order_draft` rejects live and logs paper approval only | Preserve disabled automatic execution policy. |

## 5. Recommended Development Priority

Keep the order aligned to the master guide:

1. Define asset universe.
2. Define account constraint model.
3. Build data pipeline.
4. Build feature layer.
5. Build score layer.
6. Build backtest engine.
7. Build macro regime engine.
8. Build sector scoring engine.
9. Build risk budget engine.
10. Build allocation engine.
11. Build rebalancing engine.
12. Build reporting/audit layer.
13. Generate order candidates.
14. Add user-approved execution only.
15. Consider limited automatic execution only after all safety requirements are met.

Near-term work should focus on making the existing backtest and score components safer and more reproducible before adding any new execution capability.

## 6. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q002-001 | What schema should govern asset universe and strategy parameter approvals? | Prevents unreviewed parameter or asset changes from affecting allocation. | `REVIEW_REQUIRED` for unversioned parameter changes. |
| Q002-002 | Which account types and product restrictions must be modeled first? | Hard constraints must precede order candidates and future execution. | `NO_ACTION` for candidates without validated account constraints. |
| Q002-003 | What data release calendar and revision policy should backtests use? | Prevents future-data leakage and unreproducible validation. | `HOLD` when release timing is unknown. |
| Q002-004 | What is the canonical score output schema for all strategy engines? | Enables consistent audit, confidence, and data-quality handling. | `REVIEW_REQUIRED` before promoting new score logic. |
| Q002-005 | Should automatic market-data collection during backtest runs remain enabled? | It may reduce friction but can weaken reproducibility. | `REVIEW_REQUIRED` when coverage is missing. |
| Q002-006 | Should the order API wording distinguish approval logs from broker execution? | Avoids operational confusion around `/api/orders/execute`. | Keep broker execution disabled and describe approval as log-only. |

