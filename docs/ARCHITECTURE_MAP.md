# Architecture Map

## 1. Target Architecture

The target decision flow is:

```text
Raw Data
-> Feature Layer
-> Score Layer
-> Macro Regime Score Distribution
-> Sector / Asset Score
-> Risk Budget Score
-> Allocation Score
-> Rebalancing Intensity Score
-> Hard Constraint Filter
-> Order Candidate
-> User Review
```

Execution is intentionally excluded from the default target flow. Any future execution behavior must be explicitly approved after user review, constraint filtering, audit logging, and backtest validation are complete.

## 2. Target Layer Responsibilities

| Layer | Responsibility |
|---|---|
| Data Layer | Collect, store, version, and validate raw data |
| Feature Layer | Convert raw data into normalized investment features |
| Score Layer | Convert features into comparable scores |
| Macro Regime Engine | Produce macro regime score distributions |
| Sector Scoring Engine | Score sectors/assets by attractiveness, risk, and confidence |
| Risk Budget Engine | Calculate portfolio-level and account-level risk budgets |
| Allocation Engine | Generate target allocation ranges and current target weights |
| Rebalancing Engine | Calculate rebalancing intensity and action candidates |
| Account Constraint Engine | Enforce hard account/legal/product constraints |
| Backtest Engine | Validate strategy logic historically without leakage |
| Execution Engine | Generate and validate order candidates; execute only if explicitly allowed |
| Reporting/Audit Layer | Store decision reasons, versions, warnings, and logs |

## 3. Current Repository Mapping

| Target Layer | Existing Files/Modules | Current Status | Needed Changes | Recommended Phase |
|---|---|---|---|---|
| Data Layer | `api/db.py`, `api/market_data_collector.py`, `api/market_data_service.py`, `api/macro_indicator_collector.py`, `api/macro_data_service.py`, `api/trade_data_service.py`, `api/bottleneck_data_service.py`, `data/economic_data.db`, `config/*.yaml` | partial | Separate raw, feature, score, and decision data; add data quality and source/version metadata consistently. | Phase 3 |
| Feature Layer | Implicit transformations in `api/services.py`, `api/macro_data_service.py`, `api/market_data_service.py`, and strategy engines | partial | Create explicit feature contracts and avoid embedding feature logic inside score/allocation modules. | Phase 4 |
| Score Layer | `api/strategy/macro_engine.py`, `api/strategy/bottleneck_sector_engine.py`, parts of `api/strategy/risk_budget_engine.py` and `api/strategy/types.py` | partial | Standardize score output fields: confidence, data quality, stability, reason codes, parameter version, model version. | Phase 5 |
| Macro Regime Engine | `api/strategy/macro_engine.py` | partial | Replace single label plus threshold branches with macro regime score distribution consumed gradually. | Phase 7 |
| Sector Scoring Engine | `api/strategy/bottleneck_sector_engine.py`, `api/strategy/sector_tilt_engine.py`, `config/sector_taxonomy.yaml` | partial | Keep scoring decomposable; move hardcoded weights/cutoffs into versioned configuration; add confidence/data quality. | Phase 8 |
| Risk Budget Engine | `api/strategy/risk_budget_engine.py`, `config/strategy_profiles.yaml`, `api/services.py::get_risk_budget_items` | partial | Extend beyond portfolio buckets to account-level risk budgets and hard constraints. | Phase 9 |
| Allocation Engine | `api/strategy/triplea_allocator.py`, `config/investment_universe.yaml`, `config/strategy_profiles.yaml` | partial | Generate target ranges and gradual changes from score distributions, constraints, costs, taxes, and confidence. | Phase 10 |
| Rebalancing Engine | `api/services.py::get_target_deviations`, `get_rebalancing_suggestions`, `record_rebalance_results` | partial | Add rebalancing intensity score, cost/tax/cash checks, and hard-constraint-aware candidates. | Phase 11 |
| Account Constraint Engine | `api/modes.py`, `api/providers.py`, `api/db.py` account policy tables, `api/services.py` account policy functions | partial | Create dedicated account constraint engine for account type, product, cash, risk limits, order units, and missing data states. | Phase 2 |
| Backtest Engine | `api/backtest_engine.py`, `api/services.py::run_backtest`, backtest routes in `api/main.py`, `tests/test_backtest_engine.py`, `tests/test_api_backtests.py` | partial | Harden leakage controls, release-date handling, reproducibility, turnover/cost/tax metrics, and strategy validation reporting. | Phase 6 |
| Execution Engine | `api/services.py::create_order_draft`, `approve_order_draft`, order routes in `api/main.py`, `api/kis.py`, `api/providers.py` | partial | Keep broker execution disabled; make candidate validation explicit; clarify approval-log behavior; add execution only in later approved phase. | Phase 13+ |
| Reporting/Audit Layer | `api/services.py`, `api/macro_telegram_report.py`, `api/telegram_service.py`, `api/db.py` alert/order/backtest tables, `web/app/*` pages | partial | Add complete decision trace: score inputs, constraints, parameter/model versions, warnings, quality, and reason codes. | Phase 12 |

## 4. Current Observed Flow

Current dashboard flow:

```text
SQLite data and optional provider reads
-> api/providers.py mode routing
-> api/services.py dashboard/account/target queries
-> api/main.py response models
-> web/lib/api.ts
-> web/app/* dashboard pages
```

Current backtest flow:

```text
/api/backtests/run
-> api/services.py request validation and coverage check
-> optional api/market_data_collector.py fetch when coverage is missing
-> api/backtest_engine.py simulation
-> api/strategy/triplea_allocator.py
-> macro, sector, risk-budget engines
-> simulated trades, positions, points, decisions
-> backtest tables and API response
```

Current order-candidate flow:

```text
Target deviations
-> api/services.py::create_order_draft
-> order_drafts/order_items/order_logs tables
-> paper approval log only through approve_order_draft
-> live approval rejected
```

Current flow is not fully clear from existing files for feature ownership and data revision timing. The unclear boundary is where raw macro/trade/market data becomes normalized features versus direct score inputs.

## 5. Target Interface Boundaries

### Data -> Feature

Input:

- raw data;
- source metadata;
- as-of date;
- data quality fields.

Output:

- normalized feature values;
- feature metadata.

### Feature -> Score

Input:

- feature values;
- feature quality metadata.

Output:

- normalized score;
- confidence;
- data quality;
- stability;
- reason codes.

### Score -> Allocation

Input:

- macro score distribution;
- sector/asset scores;
- risk budget score;
- account constraints.

Output:

- target ranges;
- current target weights;
- adjustment intensity.

### Allocation -> Rebalancing

Input:

- target weights;
- current weights;
- cash;
- costs;
- tax assumptions;
- constraints.

Output:

- rebalance intensity;
- action candidates.

### Rebalancing -> Order Candidate

Input:

- rebalance candidates;
- account constraints;
- order constraints.

Output:

- reviewable order candidates only.

## 6. Missing or Ambiguous Boundaries

| Boundary | Issue | Risk | Recommended Follow-Up |
|---|---|---|---|
| Raw Data -> Feature | Feature layer is implicit inside data services and engines. | Raw or stale data may influence scores without consistent normalization/quality metadata. | Define feature contracts in Phase 4. |
| Feature -> Score | Score outputs differ across macro, sector, risk, and allocation modules. | Downstream modules cannot reliably use confidence, data quality, or stability. | Define standard score schema in Phase 5. |
| Macro Score -> Allocation | Macro label and fixed shifts are used by allocator. | Dominant label can become a threshold switch. | Build regime distribution in Phase 7 and allocation refactor in Phase 10. |
| Sector Score -> Tilt | Sector regimes trigger fixed tilt values. | Discrete tilts can create abrupt allocation changes. | Move tilt policy to versioned config and make tilt intensity score-based. |
| Allocation -> Account Constraints | Account constraints are not a dedicated layer in allocation path. | Candidates may be generated before account/product eligibility is fully validated. | Build account constraint engine in Phase 2. |
| Rebalancing -> Order Candidate | Candidate generation uses deviation sign/amount. | Candidate logic can look like direct buy/sell without full constraint trace. | Add rebalancing intensity and hard constraint filter in Phases 11 and 13. |
| Backtest -> Data Pipeline | Backtest can trigger automatic market data collection. | Reproducibility may depend on fetch timing/source availability. | Define snapshot/reproducibility policy in Phase 3 and Phase 6. |
| Execution Naming | `/api/orders/execute` records paper approval logs, not broker submission. | Users or future agents may misread approval logs as real execution. | Clarify documentation/API naming before any execution work. |

## 7. Architecture Risks

- Direct raw data to order path was not observed, but feature and score boundaries are still too implicit.
- Strategy logic is mixed with threshold interpretation in macro and sector tilt modules.
- Execution-adjacent order candidate generation lives near dashboard services; future work must avoid adding broker submission there without a dedicated execution phase.
- Hardcoded parameters exist in strategy code and should not be copied into new logic.
- Decision logs exist but lack complete score/data/parameter version contracts.
- Account constraints are partial and not yet a first-class layer.
- Backtest separation exists, but release-date, data revision, and reproducible snapshot policies are incomplete.
- Current mode policy is a useful safety boundary; changing it before Phase 14 would violate the sequence policy.

## 8. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q004-001 | Should feature and score contracts be represented as Pydantic models, dataclasses, or persisted schemas? | Interface choice affects testability and API persistence. | `REVIEW_REQUIRED` before implementation. |
| Q004-002 | Should order candidate generation move out of `api/services.py` into a dedicated engine later? | Improves separation between dashboard services and investment decision flow. | Keep current behavior; do not add broker submission. |
| Q004-003 | Which account constraints belong in configuration versus code? | Hard constraints must be explicit and auditable. | `NO_ACTION` when account rule source is unclear. |
| Q004-004 | How should existing backtest tables evolve without breaking current tests? | The backtest engine already persists results; future schema changes need migration discipline. | Add migration/tests before changing persisted contracts. |
| Q004-005 | Should `docs/phase0/` task files be moved to `DevelopPlans/phase0/`? | The canonical status file now uses `DevelopPlans/STATUS.md`, but source task files currently live under `docs/phase0/`. | Leave files in place until a dedicated documentation-structure task. |

