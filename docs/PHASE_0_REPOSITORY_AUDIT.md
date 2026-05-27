# Phase 0 Repository Audit

## 1. Repository Summary

- Main language: Python for the FastAPI backend; TypeScript/TSX for the Next.js frontend.
- Package manager: `pip` with `requirements.txt` for Python; `npm` with `web/package.json` and `web/package-lock.json` for the frontend.
- Test framework: `pytest` configured by `pytest.ini`; frontend linting is configured through `npm run lint`.
- Entry points: `api/main.py` for FastAPI, `web/app/page.tsx` and route pages under `web/app/` for Next.js, `scripts/start_dashboard.sh` for local dual-server startup, and `docker-compose.yml` for container startup.
- Data storage: SQLite database at `data/economic_data.db` by default via `api/db.py`; runtime path can be overridden by `DB_PATH`.
- Existing broker/API modules: `api/kis.py` contains read-only Korean Investment Securities balance queries; `api/providers.py` routes mock, test, backtest, paper, and live modes; `api/telegram_service.py` and `api/macro_telegram_report.py` provide notification/reporting integration.
- Existing backtest modules: `api/backtest_engine.py`, `api/services.py::run_backtest`, `api/market_data_service.py`, `api/market_data_collector.py`, and API routes in `api/main.py`.
- Existing allocation/scoring modules: `api/strategy/macro_engine.py`, `api/strategy/bottleneck_sector_engine.py`, `api/strategy/sector_tilt_engine.py`, `api/strategy/risk_budget_engine.py`, `api/strategy/triplea_allocator.py`, and YAML config under `config/`.
- Existing reporting/logging modules: Dashboard API responses in `api/services.py`, alert/report tables in `api/db.py`, Telegram report helpers, order/backtest log tables, and frontend views under `web/app/`.

## 2. Directory Map

| Path | Observed Purpose | Notes |
|---|---|---|
| `api/` | FastAPI backend, service layer, DB helpers, provider routing, broker read integration, backtest, market data, and strategy modules. | Main strategy and execution-boundary logic lives here. |
| `api/strategy/` | Macro, sector, risk-budget, and allocation engines. | Mix of score-style components and threshold/regime branches. |
| `config/` | YAML and Python configuration for indicators, strategy profiles, universes, sectors, and environment settings. | Strategy profiles and universe definitions are configurable. |
| `data/` | Runtime SQLite database and data placeholder. | Contains `economic_data.db`; production-like runtime data is present locally. |
| `docs/` | Current development guide, status, phase task files, and API reference material. | Current status file is `docs/STATUS.md`; older task text still refers to `DevelopPlans/STATUS.md`. |
| `scripts/` | Setup, dashboard startup, historical data collection, cron installation, and macro report script. | Some scripts can call data/reporting services but no code edits were made in this task. |
| `tests/` | Backend pytest suite. | Covers modes, API endpoints, orders, backtests, market data, KIS provider parsing, and strategy engines. |
| `web/` | Next.js dashboard frontend. | Route pages exist for accounts, macro, portfolio, targets, backtests, orders, documents, alerts, calendar, reports, and settings. |
| `API_KEY/` | Local credential files. | Sensitive local files; should remain out of documentation detail and source control review. |
| `.venv/`, `web/node_modules/`, `web/.next/`, `.pytest_cache/` | Local generated dependency/build/cache directories. | Not investment logic. |

## 3. Important Files

| File | Observed Role | Investment-Relevant? | Notes |
|---|---|---:|---|
| `AGENTS.md` | Operational rules for Codex work. | No | Requires one-task-only, minimal safe changes, no live execution additions. |
| `docs/MASTER_DEVELOPMENT_GUIDE.md` | Architecture and strategy principles. | Yes | Defines score flow, hard constraints, backtest-before-execution, explainability, and conservative fallback expectations. |
| `docs/STATUS.md` | Current phase/task tracking. | No | Updated for this audit; notes that older task text still references `DevelopPlans/STATUS.md`. |
| `README.md` | Project overview, run commands, modes, APIs, and validation commands. | Yes | States live mode is read-only and order flow is candidate/manual approval oriented. |
| `pytest.ini` | Pytest configuration. | No | Sets `testpaths = tests` and `pythonpath = .`. |
| `requirements.txt` | Python dependency list. | No | Includes FastAPI, uvicorn, requests, python-dotenv, PyYAML, pytest. |
| `web/package.json` | Frontend scripts and dependencies. | No | Provides `dev`, `build`, `start`, and `lint`; no markdown/doc lint script observed. |
| `api/main.py` | FastAPI route definitions. | Yes | Exposes dashboard, account, rebalancing, order draft/approval, backtest, strategy metadata, market data, and system endpoints. |
| `api/modes.py` | Trading-mode policy. | Yes | Separates mock/test/backtest/paper/live write and order policy. Live is read-only until manual approval by policy string. |
| `api/providers.py` | Mode-aware provider router and KIS account sync. | Yes | Paper/live providers sync KIS balances into DB; no order placement observed. |
| `api/kis.py` | Read-only KIS OpenAPI client. | Yes | Contains token and domestic balance query helpers; module docstring says no order placement helpers. |
| `api/services.py` | Dashboard, rebalancing, order draft, order approval-log, backtest persistence, and query services. | Yes | Paper order approval records `APPROVED_NOT_SENT`; live approval is rejected. |
| `api/backtest_engine.py` | Portfolio backtest engine. | Yes | Rebalances simulated quantities using market prices, FX, fees, slippage, and tax bps. |
| `api/market_data_service.py` | Asset/price/FX lookup and coverage validation. | Yes | Uses on-or-before price/FX helpers and coverage checks for backtests. |
| `api/market_data_collector.py` | Historical market data collection. | Yes | Can collect Yahoo/FRED data when backtest coverage is missing. |
| `api/macro_data_service.py` | Macro snapshot and history services. | Yes | Provides as-of macro inputs to macro engine and dashboard. |
| `api/macro_indicator_collector.py` | Macro indicator collection. | Yes | Collects external macro data for DB storage. |
| `api/bottleneck_data_service.py` | Trade and bottleneck sector data access. | Yes | Feeds bottleneck sector scoring. |
| `api/trade_data_service.py` | Trade data access. | Yes | Feeds sector scoring inputs. |
| `api/strategy/macro_engine.py` | Macro regime scoring. | Yes | Uses hard threshold branches on VIX, PMI, yield curve, and unemployment to produce a score and regime label. |
| `api/strategy/bottleneck_sector_engine.py` | Sector bottleneck scoring. | Yes | Blends trade, demand, supply, and relative-strength scores; classifies regimes with thresholds. |
| `api/strategy/sector_tilt_engine.py` | Applies sector tilts to asset weights. | Yes | Applies fixed max tilts based on sector regimes and halves tilt in risk-off. |
| `api/strategy/risk_budget_engine.py` | Bucket min/max enforcement. | Yes | Clamps bucket weights to configured min/max rules. |
| `api/strategy/triplea_allocator.py` | Dynamic allocator orchestration. | Yes | Combines macro, sector, tilt, and risk budget outputs into final weights. |
| `config/strategy_profiles.yaml` | Risk profile bucket targets/min/max. | Yes | Strategy parameters are externalized here. |
| `config/investment_universe.yaml` | Asset universe, buckets, currencies, source types, sectors. | Yes | Asset candidates are configuration-driven. |
| `config/sector_taxonomy.yaml` | Sector definitions and indicators. | Yes | Supports sector scoring. |
| `config/backtest_assets.yaml` | Backtest asset metadata/mapping seed source. | Yes | Used by DB seeding and market-data universe. |
| `tests/test_modes.py` | Mode policy and DB schema tests. | Yes | Confirms order boundaries and mode provider routing. |
| `tests/test_api_orders.py` | Order draft and approval behavior tests. | Yes | Relevant to no-live-execution boundary. |
| `tests/test_backtest_engine.py` | Backtest engine tests. | Yes | Relevant to backtest capability and assumptions. |
| `tests/test_macro_engine.py`, `tests/test_bottleneck_sector_engine.py`, `tests/test_sector_tilt_engine.py`, `tests/test_risk_budget_engine.py`, `tests/test_triplea_allocator.py` | Strategy engine tests. | Yes | Cover current scoring/allocation behavior. |
| `web/lib/api.ts` | Frontend API client. | Yes | Includes order draft, execute, sync, backtest, and dashboard calls. |
| `scripts/start_dashboard.sh` | Local development startup script. | No | Starts FastAPI on 8000 and Next.js on 3000. |

## 4. Current Execution Flow

Observed dashboard flow:

```text
SQLite/runtime data and optional external reads
→ api/services.py dashboard queries
→ provider_router mode selection
→ FastAPI response models
→ web/lib/api.ts
→ Next.js dashboard pages
```

Observed backtest flow:

```text
BacktestRunRequest
→ api/services.py validates options and market data coverage
→ optional historical market data collection when coverage is missing
→ BacktestEngine
→ TripleAAllocator
→ MacroEngine + BottleneckSectorEngine + SectorTiltEngine + RiskBudgetEngine
→ simulated rebalance trades/positions/points
→ SQLite backtest tables
→ API/frontend result views
```

Observed order-candidate flow:

```text
Current holdings/account snapshots and target deviations
→ rebalancing result calculation
→ /api/orders/draft creates draft order candidates
→ /api/orders/execute records paper approval only when explicit Korean confirm text is supplied
→ no broker order submission observed
```

Target reference from the master guide is only partially met today:

```text
Raw data
→ preprocessing / feature generation
→ score calculation
→ allocation / decision
→ report / candidate output
→ execution only if explicitly enabled later
```

The actual flow has score and allocation components, but several rules still use direct threshold branches or fixed shifts. Hard account constraints are partly represented by mode policy and risk-budget min/max checks, but account/legal/product constraints are not yet a comprehensive first-class filter in the observed allocation path.

## 5. Existing Strategy Logic

| Location | Logic Summary | Classification | Risk |
|---|---|---|---|
| `api/strategy/macro_engine.py` | Starts at score 50 and adjusts based on VIX, PMI, yield curve, unemployment; maps score/VIX to `risk_off`, `cautious`, `risk_on`, or `neutral`. | threshold-based | Single-indicator threshold branches can dominate regime classification, especially VIX. |
| `api/strategy/triplea_allocator.py::_macro_adjusted_profile` | Shifts fixed bucket weights between aggressive, defensive, and liquidity buckets for risk-off/cautious/risk-on labels. | hardcoded | Uses fixed shift amounts and regime labels rather than continuous regime distributions. |
| `api/strategy/bottleneck_sector_engine.py` | Combines trade, demand, supply, and relative-strength scores using fixed weights, then classifies sector regime by score thresholds. | score-based with threshold classification | Score blending exists, but component weights and regime cutoffs are hardcoded in code. |
| `api/strategy/sector_tilt_engine.py` | Applies fixed sector tilts for `active` and `emerging` regimes, capped by max total/sector tilt; halves tilt in risk-off. | threshold-based / hardcoded | Regime labels trigger discrete tilts; policy defaults are hardcoded dataclass values. |
| `api/strategy/risk_budget_engine.py` | Normalizes asset weights and clamps bucket weights to configured min/max rules. | score-based support / hard constraint-like | Good min/max enforcement, but not a full account constraint engine. |
| `config/strategy_profiles.yaml` | Defines aggressive/balanced/defensive bucket target/min/max values. | hardcoded config | Parameters are configurable but approval/version metadata is not observed. |
| `config/investment_universe.yaml` | Defines default asset universe and bucket/sector metadata. | hardcoded config | Universe is configurable, but current defaults may shape allocation heavily. |
| `api/services.py::get_target_deviations` and `get_rebalancing_suggestions` | Compares current allocations to target values and warning/danger thresholds. | threshold-based | Useful for alerts/candidates, but can become direct action logic if not constrained. |
| `api/services.py::create_order_draft` | Converts target deviation rows into BUY/SELL candidate amounts. | threshold-based candidate generation | Generates candidates, not broker execution; needs explicit hard constraints before any future execution. |
| `api/services.py::approve_order_draft` | Requires paper mode and exact confirm text; writes `APPROVED_NOT_SENT`. Live mode is rejected. | not investment logic | Safety boundary is clear; name `/execute` may imply execution despite logging only. |
| `api/backtest_engine.py` | Simulates periodic rebalances to allocator output using historical prices and costs. | score-based consumer | Needs continued leakage checks and explicit treatment of data availability/revisions. |
| `api/kis.py` | Fetches token and domestic balance snapshots from KIS. | not investment logic | External API read path exists; credentials and network errors must remain conservative. |

## 6. Existing Backtest Capability

- Backtest entry point: `POST /api/backtests/run` in `api/main.py`, implemented by `api/services.py::run_backtest` and `api/backtest_engine.py::BacktestEngine`.
- Data assumptions: Uses assets from configured universe, price data from `market_prices`, FX data from `fx_rates`, and macro/sector data from local DB services. If market coverage is missing, `run_backtest` attempts collection through `collect_for_asset_codes`.
- Output metrics: Total return, annual return, max drawdown, volatility, portfolio value points, positions, trades, allocation decisions, bucket/final weights, bottleneck scores, and decision reasons are persisted and returned.
- Leakage protection observed: Market price and FX helpers include on-or-before lookup behavior; backtest date validation and coverage checks exist. Macro and sector services are queried as of `as_of_date`.
- Current limitations: Macro regime logic uses threshold labels rather than a full score distribution; parameter metadata/versioning is not observed in backtest results; data revision timing and release-lag treatment are not fully documented; automatic data collection during backtest may obscure reproducibility unless source/fetch metadata is reviewed.

## 7. Existing Execution or Broker API Capability

- Broker/API files: `api/kis.py`, `api/providers.py`, `api/modes.py`, KIS-related tests, `.env.example`, and local `API_KEY/` files.
- Order-related functions: `api/services.py::create_order_draft`, `api/services.py::approve_order_draft`, API routes `/api/orders/draft`, `/api/orders/execute`, `/api/orders/drafts`, DB tables `order_drafts`, `order_items`, and `order_logs`.
- Mock/paper trading behavior: Paper mode can sync KIS paper balances and create order drafts. Paper approval requires exact confirm text and records `APPROVED_NOT_SENT`; the log message states broker submission is not implemented.
- Real trading behavior: Live mode can sync KIS live balances in read-only mode. `approve_order_draft` rejects live mode with "Live order execution is disabled; this mode remains read-only." No broker order placement helper was observed in `api/kis.py`.
- Safety concerns: `ModePolicy.can_execute_orders` returns true only for `paper_order` or `manual_live_order`; current live policy is `read_only_until_manual_approval`, so it evaluates false. The endpoint name `/api/orders/execute` and frontend method `executeOrderDraft` may still be operationally confusing because paper approval logs are not actual broker execution.

## 8. Current Risk Areas

- Score Flow: Partially implemented. Sector and allocator flows use score-like objects, but macro regime and sector tilt still contain threshold/regime switches and fixed shifts.
- Hard Constraints First: Partially implemented through mode policies and risk bucket min/max checks. A dedicated account constraint engine for account type, product eligibility, cash, minimum unit, and legal restrictions was not observed.
- Backtest Before Execution: Backtest capability exists and live execution is disabled. Future work should require backtest evidence before enabling any new order behavior.
- No automatic execution by default: No broker order submission was observed. Paper approval writes logs only; live approval is rejected.
- No hardcoded strategy parameters: Not fully met. Many parameters are in YAML, but macro thresholds, macro shift amounts, sector score weights, and default tilt policy values are hardcoded in Python.
- No future-data leakage: Some on-or-before lookup behavior exists. Data release timing, revisions, survivorship bias, and automatic data collection reproducibility remain open risks.
- Explainability requirement: Decisions persist reasons, macro reasons, bottleneck reasons, and order reasons. Standard score output metadata such as confidence, data quality, stability, parameter version, and model version is not consistently present.
- Conservative fallback behavior: Some conservative behavior is present through read-only modes and config errors. Missing strategy parameters often raise errors rather than returning a documented `NO_ACTION`, `HOLD`, `REVIEW_REQUIRED`, or `RISK_REDUCE_ONLY` state.
- Secret handling: Local `API_KEY/` files and `.env` exist in the working tree. They should not be exposed in logs, generated docs, or commits.
- Repository state: The working tree already contains deleted legacy docs and untracked new docs before this task. This audit did not revert or normalize those unrelated changes.

## 9. Open Questions

| ID | Question | Why It Matters | Conservative Default |
|---|---|---|---|
| Q000-001 | Should `docs/STATUS.md` fully replace the older `DevelopPlans/STATUS.md` path referenced by task files? | Automation may look for the old path and miss current task state. | `REVIEW_REQUIRED`; update the actual observed `docs/STATUS.md` only. |
| Q000-002 | What is the approved parameter/version metadata format for strategy profiles, macro thresholds, and sector tilt policies? | The master guide requires parameter management and traceability. | `HOLD` on parameter changes without metadata. |
| Q000-003 | Should macro regime become a distribution object instead of a single label plus score? | The master guide prohibits dominant regime labels driving allocation directly. | `REVIEW_REQUIRED` before changing allocation behavior. |
| Q000-004 | What account constraint rules are required for each account type and product universe? | Hard constraints should precede candidate generation and any future execution. | `NO_ACTION` for candidates that cannot be validated. |
| Q000-005 | How should macro data release lag and revisions be represented in backtests? | Prevents future-data leakage and improves reproducibility. | `HOLD` or reduce confidence when release timing is unknown. |
| Q000-006 | Should `/api/orders/execute` be renamed or clarified since it does not submit broker orders? | Reduces operational confusion around live/paper behavior. | Keep broker submission disabled and document approval as log-only. |
| Q000-007 | Which external data collection calls are acceptable during backtest runs? | Automatic collection may make repeated backtests non-reproducible. | `REVIEW_REQUIRED` when data coverage is missing. |
| Q000-008 | Which files under `API_KEY/` and `.env` are intentionally local-only, and are they fully ignored by Git? | Prevents credential leakage. | Do not read, print, or commit secret contents. |
