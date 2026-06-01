# Live Integration Pruning Manifest

This manifest records live account, broker, execution, and external-service
candidates before any deletion. It is intentionally analysis-only: no source,
test, or config file is removed by Task 002.

Canonical development rules remain in `MASTER_DEVELOPMENT_GUIDE.md`. The
simplification contract is in `docs/simplification/SIMPLIFIED_ARCHITECTURE.md`.

## Inspection Summary

Commands used for this manifest:

```bash
find . -maxdepth 3 -type f | sort
find tests -maxdepth 2 -type d | sort
rg -n -i --glob '!API_KEY/**' --glob '!.env' --glob '!web/node_modules/**' --glob '!web/.next/**' --glob '!**/__pycache__/**' --glob '!.pytest_cache/**' "kis|broker|brokers|execution|executor|live|paper|account sync|balance sync|order execute|place_order|approval|telegram|slack|websocket|API_KEY|ACCESS_TOKEN|APP_KEY|APP_SECRET" api tests config scripts web README.md MASTER_DEVELOPMENT_GUIDE.md AGENTS.md DevelopPlans
rg -n --glob '!web/node_modules/**' --glob '!web/.next/**' --glob '!**/__pycache__/**' "api\\.providers\\.(live|paper)|api\\.providers|api\\.brokers|from api\\.telegram_service|import api\\.telegram_service|from api\\.macro_telegram_report|import api\\.macro_telegram_report|place_order|sync-accounts|LiveTradingProvider|PaperTradingProvider|KIS|kis" api tests config scripts web README.md DevelopPlans
```

Local secret/runtime directories exist (`.env`, `API_KEY/`, `.pytest_cache/`,
`web/.next/`, `web/node_modules/`, `__pycache__/`). Their contents were not
read for this manifest and they must not be committed.

## delete_live_integration

These files are direct live, paper, or broker-account integration candidates.
Owner decision: all-A deletion; future implementation only, no current
adapter/stub retention.

| File | Basis | Expected impact | Import/use references |
|---|---|---|---|
| `api/brokers/kis/client.py` | KIS token issuance and domestic balance request client; uses network `requests` and balance endpoint. | Removing it breaks KIS account sync and tests that parse/sync KIS balances. | Imported by `api/providers/live.py`, `api/providers/paper.py`, `api/market_data/price_provider.py`, `tests/test_kis_provider.py`, `tests/brokers/kis/test_client_imports.py`. |
| `api/brokers/kis/config.py` | Loads KIS app credentials/account identifiers from env and `.env`. | Removing it breaks KIS account sync and current read-only price provider helper imports. | Imported by KIS client, `api/market_data/price_provider.py`, KIS tests. |
| `api/brokers/kis/errors.py` | Broker-specific KIS error surface. | Removing it requires replacing API route error handling and tests. | Imported by `api/features/system/router.py`, KIS tests, provider tests. |
| `api/brokers/kis/models.py` | KIS balance snapshot/position value objects tied to broker balance sync. | Removing it requires local account fixtures or simulated account models to replace broker-shaped snapshots. | Imported by KIS client, `api/providers/_upsert.py`, KIS tests. |
| `api/providers/live.py` | Live KIS account sync provider. | Removing it changes `live` mode behavior and `/api/providers/live/sync-accounts`. | Imported by `api/providers/router.py`, `tests/providers/test_kis_providers.py`. |
| `api/providers/paper.py` | Paper KIS account sync provider. | Removing it changes `paper` mode behavior and `/api/providers/paper/sync-accounts`. | Imported by `api/providers/router.py`, `tests/providers/test_kis_providers.py`. |
| `api/providers/_upsert.py` | Persists KIS balance snapshots into local accounts, holdings, and snapshots. | Removing it requires a non-broker local/simulated account refresh path. | Imported by `api/providers/live.py`, `api/providers/paper.py`. |
| `api/providers/**` | Owner decision: all-A deletion; future implementation only, no current adapter/stub retention. Provider compatibility shims are forbidden. | Removes provider layer, paper/live modes, and local provider routing. Remaining features must use deterministic local queries or backtest/simulation contracts, not provider compatibility shims. | Imported by accounts, dashboard, system, alerts, rebalancing, targets, orders, tests, and web mode contracts. |
| `api/features/orders/**` | Owner decision: all-A deletion; future implementation only, no current adapter/stub retention. Order candidate API/feature stubs are forbidden. | Removes order drafts, order approval logs, and order feature API. Allowed outputs remain local `DecisionSnapshot`, `RebalancePlan`, `BacktestReport`, or `AuditLog`. | Used by orders routers/tests and web orders page. |
| `api/market_data/price_provider.py` | Owner decision: all-A deletion for KIS read-only price adapters and credential/env dependency. Disabled KIS adapters are forbidden. | Removes KIS/env-backed read-only price provider; deterministic fixtures or mock/local price paths must be used instead. | Imports `api.brokers.kis.config` and `api.brokers.kis.client`. |
| `api/data/adapters/kis_readonly.py` | Owner decision: all-A deletion for KIS read-only adapters. Disabled KIS adapter retention is forbidden. | Removes KIS external market-data adapter and endpoint allowlist. Fixture/local data adapters must replace it in tests. | Used by `tests/data/adapters/test_kis_readonly_adapter.py` and `config/data_sources/capex_cycle_sources.yaml`. |
| `api/telegram_service.py` | Owner decision: all-A deletion for Telegram/reporting feature/API. Disabled Telegram adapters are forbidden. | Removes external Telegram notification delivery. Local output contracts may keep reason codes/warnings only. | Imported by alerts service, macro router, macro report tests. |
| `api/macro_telegram_report.py` | Owner decision: all-A deletion for Telegram/reporting feature/API. Disabled reporting adapters are forbidden. | Removes Telegram macro report delivery. Local report/audit fields remain allowed only if deterministic. | Imported by macro feature repository, daily report script, macro telegram tests. |
| `scripts/send_daily_macro_report.py` | Owner decision: all-A deletion for Telegram/reporting automation. | Removes external report delivery script. | Imports `api.macro_telegram_report`. |
| `scripts/install_macro_cron.sh` | Owner decision: all-A deletion for Telegram/reporting automation. | Removes cron installer for external report delivery. | Writes cron command for Telegram script. |
| `web/app/orders/**` | Owner decision: all-A deletion for order feature and UI paper/live mode. | Removes order feature UI. No order candidate UI stub should remain. | Uses order API and paper/live mode controls. |

## delete_live_tests

These tests primarily validate KIS broker account integration or live/paper
provider wiring and should be removed or rewritten as deterministic local code
tests when the corresponding source files are removed.

| File | Basis | Expected impact | Import/use references |
|---|---|---|---|
| `tests/brokers/kis/test_client_imports.py` | Direct KIS client import and network-error behavior. | Delete or replace with deterministic non-broker parser tests if needed. | Imports `api.brokers.kis.client`, `config`, `errors`. |
| `tests/brokers/kis/test_config.py` | KIS credential/account config behavior. | Delete with broker config removal. | Imports `api.brokers.kis.config`. |
| `tests/brokers/kis/test_errors.py` | KIS-specific error classes. | Delete with broker error surface removal. | Imports `api.brokers.kis.errors`. |
| `tests/brokers/kis/test_models.py` | KIS balance snapshot model tests. | Delete or rewrite around simulated account models if a pure replacement is needed. | Imports `api.brokers.kis.models`. |
| `tests/providers/test_kis_providers.py` | Paper/live provider import and credential-error behavior. | Delete or replace with simplified provider/router contract tests. | Imports `api.providers.live`, `api.providers.paper`, `api.brokers.kis.errors`. |
| `tests/test_kis_provider.py` | KIS config/client parsing and paper/live sync-to-DB tests. | Delete or split into deterministic local account ingestion tests if preserving useful parser assertions. | Imports KIS broker modules and `ProviderRouter`. |
| `tests/providers/**` | Owner decision: all-A deletion for `api/providers`. | Remove provider layer tests; replace with deterministic local contract tests only if needed by later tasks. | Imports `api.providers.*`. |
| `tests/data/adapters/test_kis_readonly_adapter.py` | Owner decision: all-A deletion for KIS read-only adapters. | Delete with `api/data/adapters/kis_readonly.py`. | Imports `api.data.adapters.kis_readonly`. |
| `tests/features/orders/**` | Owner decision: all-A deletion for orders feature. | Delete with `api/features/orders/**`; no order candidate feature stub should remain. | Imports orders feature. |
| `tests/test_macro_telegram_report.py` | Owner decision: all-A deletion for Telegram/reporting feature/API. | Delete with Telegram report delivery code. | Imports `api.macro_telegram_report` and `api.telegram_service`. |

## keep_domain_contract

These files contain pure or mostly pure account, constraint, schema, or
simulation contracts. They should not be removed as part of broker pruning.

| File | Basis | Expected impact | Import/use references |
|---|---|---|---|
| `config/account_constraints.yaml` | Account constraint data for hard-constraint validation. | Keep; needed for simulated/backtest hard constraints. | Used by domain/config tests. |
| `api/features/accounts/models.py` | Account feature domain models. | Keep unless later UI/API simplification explicitly removes account pages. | Used by accounts service/router/tests. |
| `api/features/accounts/schemas.py` | Account feature public schemas, including local/manual snapshots. | Keep local/manual account behavior; review provider-router coupling separately. | Used by accounts feature and provider base. |
| `api/features/accounts/ports.py` | Account feature port contract. | Keep as vertical-slice contract. | Used by account service/dependencies/tests. |
| `api/features/accounts/service.py` | Account service orchestration without direct broker imports. | Keep; repository dependency may need simplification later. | Used by accounts router/tests. |
| `tests/features/accounts/test_contracts.py` | Local account contract tests. | Keep if they do not require broker credentials/network. | Uses account schemas/models. |
| `tests/features/accounts/test_service.py` | Account service behavior tests. | Keep if they remain local/deterministic. | Uses account feature service. |

## keep_backtest

These files are backtest or simulation related and are explicitly preserved by
the simplified architecture unless a later task finds a small live dependency to
disconnect.

| File | Basis | Expected impact | Import/use references |
|---|---|---|---|
| `api/backtest_engine.py` | Existing backtest engine and runner. | Keep; final architecture depends on backtests. | Used by `api/features/backtests/dependencies.py` and backtest tests. |
| `api/backtest_foundation.py` | Backtest foundation contracts. | Keep. | Used by backtest tests. |
| `api/features/backtests/**` | Backtest vertical slice. | Keep; Task 006/007 depend on backtest outputs. | Used by API and feature tests. |
| `config/backtest/**` | Backtest config. | Keep. | Used by backtest foundation tests. |
| `config/backtests/**` | Sector/component backtest configs and fixtures. | Keep; contains explicit no-live guardrail fields. | Used by sector component backtest tests. |
| `tests/backtest/**` | Supported backtest suite. | Keep unless a specific test is later proven live/external-only. | Current tests include no account/order/execution output guardrails. |
| `tests/fixtures/backtests/**` | Deterministic backtest fixtures. | Keep. | Used by backtest tests. |

## keep_code_tests

These tests are deterministic code, architecture, unit, or integration tests and
should remain supported unless a later task identifies a specific external
dependency.

| File | Basis | Expected impact | Import/use references |
|---|---|---|---|
| `tests/architecture/**` | Import-boundary and architecture guardrails. | Keep and extend in Task 008. | Includes existing no-live/default-execution checks. |
| `tests/integration/pipeline/**` | Deterministic pipeline integration tests. | Keep for input-to-output validation. | Uses fixture-backed pipeline data. |
| `tests/unit/**` | Unit tests for pure contracts. | Keep. | Unit-level deterministic checks. |
| `tests/score_pipeline/**` | Score pipeline and plugin contract tests. | Keep if no external service is required. | Existing tests guard against broker/order imports. |
| `tests/test_price_provider_contract.py` | Ensures price providers have no order methods. | Keep or adapt to simplified provider set. | Guards against order surface. |
| `tests/test_no_live_execution_guardrails.py` | Guardrail against order/execution terms in universe and market-data code. | Keep and extend in Task 008 if compatible. | Static scan. |

## owner_decision_all_a_reclassified

The following files or groups were previously `review_required`. They are now
classified as deletion targets by owner decision.

Owner decision: all-A deletion; future implementation only, no current
adapter/stub retention.

Forbidden retention patterns:

- provider compatibility shim
- disabled KIS adapter
- disabled Telegram/reporting adapter
- paper/live UI mode stub
- order candidate API/feature stub

| File or group | Why review is required | Expected impact | Import/use references |
|---|---|---|---|
| `api/providers/**` | Previously mixed local and paper/live behavior. | Delete; do not preserve provider compatibility shim. | Accounts, dashboard, system, alerts, rebalancing, targets, orders, tests, web mode contracts. |
| `api/features/system/router.py` sync route and KIS error handling | Provider sync and KIS-specific errors are removed. | Remove `/api/providers/{mode}/sync-accounts`; preserve unrelated health/status routes if possible. | Imports KIS errors and provider modes. |
| `api/features/system/repository.py` provider-mode methods | Provider mode listing/sync depends on deleted provider router. | Remove provider-mode methods or replace with local app state only where needed for collection. | Imported by system service/router/tests. |
| `api/features/system/schemas.py` provider sync/mode schemas | Provider sync/mode API is removed. | Delete or simplify only if unused by remaining local API. | Used by providers and system tests. |
| `api/features/accounts/repository.py` provider-router reads | Account local/manual behavior can remain, but provider-router dependency must be removed. | Replace with direct local deterministic SQL reads if account feature remains. | Used by account service/router/tests. |
| `api/features/dashboard/repository.py` provider-router reads and paper/live mode info | UI paper/live mode is removed. | Replace with local/simulation-only dashboard data if dashboard remains. | Used by dashboard route/tests/UI. |
| `api/features/rebalancing/repository.py` provider-router reads | Rebalancing remains simulation-only; provider dependency is deleted. | Replace target deviation lookup with local deterministic logic if needed. | Used by rebalancing tests/API. |
| `api/features/targets/repository.py` provider-router usage | Provider dependency is removed. | Replace with local deterministic target reads if target feature remains. | Imported by targets feature. |
| `api/features/alerts/repository.py` provider-router usage and Telegram paths | External notification/reporting is removed. | Keep local alerts only if they do not require provider or Telegram. | Imported by alerts feature/tests. |
| `api/features/orders/**` | Order candidate API/feature is removed. | Delete; do not replace with order stubs. | Orders page/tests. |
| `web/lib/types.ts` paper/live modes | UI paper/live modes are removed. | Keep only local/backtest/simulation mode types if UI remains. | Used across web UI. |
| `web/lib/api.ts` provider sync and order API calls | Provider sync and order API are removed. | Delete or update affected client functions. | Dashboard/account/system/orders UI. |
| `web/app/orders/**` | Order UI is removed. | Delete; no paper/live/order stub. | Uses order API and paper/live controls. |
| `web/components/dashboard/DashboardClient.tsx` paper/live presentation | UI paper/live mode is removed. | Replace with local/backtest/simulation presentation if dashboard remains. | Uses dashboard API response. |
| `api/market_data/price_provider.py` | KIS/env-backed price provider is removed. | Delete or replace with non-provider local fixture path only if required by tests. | Price provider tests and market-data call sites. |
| `api/data/adapters/kis_readonly.py` | KIS read-only adapter is removed. | Delete and remove config/test references. | KIS read-only adapter tests and capex source config. |
| `config/data_sources/capex_cycle_sources.yaml` `kis_readonly` entries | KIS read-only source group is removed. | Remove entries or replace with fixture/local source only if existing deterministic tests require it. | Capex source config tests. |
| `config/settings.py` and `config/__init__.py` KIS/Telegram settings | External service settings are removed when no remaining non-live code uses them. | Remove KIS/Telegram-only settings while preserving non-live data keys if still used. | Setup/tests/config imports. |
| `api/telegram_service.py`, `api/macro_telegram_report.py` | Telegram/reporting feature/API is removed. | Delete; no disabled Telegram/reporting adapter. | Macro feature, alerts service, script, tests. |
| `scripts/send_daily_macro_report.py`, `scripts/install_macro_cron.sh` | External report delivery automation is removed. | Delete. | Macro Telegram report script/cron. |
| `tests/test_api_endpoints.py` provider-sync/KIS parts | Mixed tests must be split or rewritten. | Remove provider-sync/KIS assertions, keep unrelated local API assertions. | Provider router and KIS errors. |
| `tests/providers/**`, `tests/test_modes.py` | Provider tests are removed. | Delete or replace with local deterministic tests in later tasks. | Imports `api.providers.*`. |
| `tests/features/orders/**` | Orders feature tests are removed. | Delete. | Imports orders feature. |
| `tests/features/alerts/**`, `tests/test_macro_telegram_report.py` external notification parts | Telegram/reporting tests are removed; local alert tests can remain only without provider/Telegram. | Split or delete external notification parts. | Alert/macro Telegram services. |
| `README.md` KIS, paper/live, orders, provider sync docs | Documentation must be updated after code deletion. | Rewrite stale references during final docs task. | Root documentation only. |

## Remaining Review Items Outside Owner Scope

None recorded in this manifest. If new owner decisions are discovered during
deletion, stop only when the issue is outside the owner all-A scope or would
require removing score flow, backtest engine, or deterministic data-to-output
contracts.
