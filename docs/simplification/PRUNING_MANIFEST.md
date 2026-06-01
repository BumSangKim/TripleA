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
They should be deleted or disconnected only after the `review_required`
couplings below are resolved.

| File | Basis | Expected impact | Import/use references |
|---|---|---|---|
| `api/brokers/kis/client.py` | KIS token issuance and domestic balance request client; uses network `requests` and balance endpoint. | Removing it breaks KIS account sync and tests that parse/sync KIS balances. | Imported by `api/providers/live.py`, `api/providers/paper.py`, `api/market_data/price_provider.py`, `tests/test_kis_provider.py`, `tests/brokers/kis/test_client_imports.py`. |
| `api/brokers/kis/config.py` | Loads KIS app credentials/account identifiers from env and `.env`. | Removing it breaks KIS account sync and current read-only price provider helper imports. | Imported by KIS client, `api/market_data/price_provider.py`, KIS tests. |
| `api/brokers/kis/errors.py` | Broker-specific KIS error surface. | Removing it requires replacing API route error handling and tests. | Imported by `api/features/system/router.py`, KIS tests, provider tests. |
| `api/brokers/kis/models.py` | KIS balance snapshot/position value objects tied to broker balance sync. | Removing it requires local account fixtures or simulated account models to replace broker-shaped snapshots. | Imported by KIS client, `api/providers/_upsert.py`, KIS tests. |
| `api/providers/live.py` | Live KIS account sync provider. | Removing it changes `live` mode behavior and `/api/providers/live/sync-accounts`. | Imported by `api/providers/router.py`, `tests/providers/test_kis_providers.py`. |
| `api/providers/paper.py` | Paper KIS account sync provider. | Removing it changes `paper` mode behavior and `/api/providers/paper/sync-accounts`. | Imported by `api/providers/router.py`, `tests/providers/test_kis_providers.py`. |
| `api/providers/_upsert.py` | Persists KIS balance snapshots into local accounts, holdings, and snapshots. | Removing it requires a non-broker local/simulated account refresh path. | Imported by `api/providers/live.py`, `api/providers/paper.py`. |

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
| `tests/data/adapters/test_kis_readonly_adapter.py` | Deterministic parser/read-only allowlist tests. | Keep only if the project explicitly keeps read-only KIS market-data adapter code; otherwise reclassify with KIS adapter deletion. | Imports `api.data.adapters.kis_readonly`. |
| `tests/test_price_provider_contract.py` | Ensures price providers have no order methods. | Keep or adapt to simplified provider set. | Guards against order surface. |
| `tests/test_no_live_execution_guardrails.py` | Guardrail against order/execution terms in universe and market-data code. | Keep and extend in Task 008 if compatible. | Static scan. |

## review_required

The following files or groups are coupled to live/paper modes, external
providers, UI contracts, or owner-unresolved reporting behavior. Because at
least one item is unclear, Task 002 must stop after this manifest and must not
continue to Task 003 until the owner decisions are made.

| File or group | Why review is required | Expected impact | Import/use references |
|---|---|---|---|
| `api/providers/base.py` | Base provider is shared by mock/test/backtest and paper/live; not itself a broker adapter. | Deleting provider concepts wholesale would break local dashboard/account reads. | Used by all provider implementations and provider tests. |
| `api/providers/modes.py` | Defines `paper` and `live` modes plus write/order policies, but also defines mock/test/backtest. | Simplification likely requires removing or redefining `paper`/`live`; public API/UI impact. | Imported by feature schemas, routers, repositories, web types/tests. |
| `api/providers/router.py` | Imports live/paper providers while also routing mock/test/backtest providers. | Needs a small replacement router or mode policy update before deleting live/paper files. | Imported by accounts, dashboard, system, alerts, rebalancing, targets, orders. |
| `api/providers/mock.py` | Local providers are allowed, but currently live in the same package as live/paper providers. | Likely keep or relocate after router simplification. | Imported by provider router and tests. |
| `api/features/system/router.py` | Exposes `/api/providers/{mode}/sync-accounts` and catches KIS errors; also owns health/status/settings routes. | Must split or disable only provider sync without breaking health/status APIs. | Imports KIS errors and provider modes. |
| `api/features/system/repository.py` | `sync_accounts`, `list_modes`, and `get_mode_info` call `provider_router`. | Requires simplified mode/provider contract. | Imported by system service/router/tests. |
| `api/features/system/schemas.py` | `ModeInfo` and `ProviderSyncResult` expose provider mode status. | Needs schema decision for simplified modes and local-only sync outputs. | Used by providers and system API tests. |
| `api/features/accounts/repository.py` | Account reads use `provider_router.get(mode)`, but manual snapshots/local accounts are allowed. | Needs local provider or direct local repository path. | Used by account service/router/tests. |
| `api/features/dashboard/repository.py` | Dashboard reads provider mode info, accounts, allocation, target deviations, top movers. | Requires simplified local/backtest provider behavior before removing provider router. | Used by dashboard route/tests/UI. |
| `api/features/rebalancing/repository.py` | Rebalancing suggestions use provider target deviations and record local results. | Keep pure simulation behavior, but remove live/paper mode dependency carefully. | Used by rebalancing service/router/tests. |
| `api/features/targets/repository.py` | Uses provider router for target state. | Needs local/simulated mode decision. | Imported by targets feature. |
| `api/features/alerts/repository.py` | Uses provider router for generated target alerts. | Needs local/test mode replacement. | Imported by alerts feature. |
| `api/features/orders/**` | Produces paper/live order drafts and manual paper approval logs; does not submit broker orders, but exposes order-like UI/API. | Simplified output contract allows `RebalancePlan`, not order drafts; product/API decision needed. | Orders page and tests exercise this feature. |
| `web/lib/types.ts` | Includes `paper` and `live` trading modes. | UI contract change required if modes are removed. | Used across web UI. |
| `web/lib/api.ts` | Calls `/api/providers/${mode}/sync-accounts`. | Must be updated if sync endpoint is removed/disabled. | Used by dashboard/account/system UI. |
| `web/app/orders/OrdersPageClient.tsx` | Shows paper/live order draft and approval UI; live is disabled but still user-facing. | Simplification likely removes or replaces with simulation/report output UI. | Uses orders API and `TradingMode`. |
| `web/components/dashboard/DashboardClient.tsx` | Displays paper/live mode labels and external API state. | Needs simplified mode UX decision. | Uses dashboard API response. |
| `api/market_data/price_provider.py` | Read-only KIS quote provider imports `api.brokers.kis` helpers and can use env credentials when explicitly enabled. | Simplification wants no external API dependency; removing it affects live price smoke tests and market-data contracts. | Imported by price-provider tests and market data call sites. |
| `api/data/adapters/kis_readonly.py` | Read-only KIS market-data adapter with endpoint guardrails; not account sync, but still a KIS external API adapter. | Needs owner decision: keep as disabled code contract or remove from simplified architecture. | Used by `tests/data/adapters/test_kis_readonly_adapter.py` and capex data-source config. |
| `config/data_sources/capex_cycle_sources.yaml` | References `kis_readonly` source group. | Removing KIS read-only adapter requires config fallback or fixture-only source. | Used by capex source config tests. |
| `config/settings.py` and `config/__init__.py` | Load KIS and Telegram/API env settings. | Removing external service settings may affect non-broker data adapters and system status. | Imported by legacy setup/tests and scripts. |
| `api/telegram_service.py`, `api/macro_telegram_report.py` | External notification/report delivery paths; owner was already unresolved in `DevelopPlans/post_legacy_gap_resolution/root_owner_decision_inventory.md`. | Simplification likely removes external service dependency, but reporting/local alert semantics need owner approval. | Imported by macro feature, alerts service, script, and tests. |
| `scripts/send_daily_macro_report.py`, `scripts/install_macro_cron.sh` | Telegram delivery automation. | Likely outside simplified test/code scope; deletion needs script/ops approval. | Imports macro Telegram report or installs cron. |
| `tests/test_api_endpoints.py` | Mixed API tests include provider sync/KIS error tests and unrelated endpoint tests. | Must split rather than delete wholesale. | Imports provider router and KIS errors in specific tests. |
| `tests/test_modes.py`, `tests/providers/test_modes.py`, `tests/providers/test_router.py`, `tests/providers/test_base.py`, `tests/providers/test_mock.py` | Provider mode tests mix allowed mock/backtest behavior with paper/live mode expectations. | Needs rewrite after mode policy decision. | Import `api.providers.*`. |
| `tests/features/orders/**` | Tests order draft/approval UI contracts. | Needs output-contract decision: delete, rewrite to `RebalancePlan`, or keep simulation-only. | Imports orders feature. |
| `tests/features/alerts/**`, `tests/test_macro_telegram_report.py` | Alerts include local behavior plus Telegram notification contracts. | Need split local alert tests from external Telegram tests. | Import alert/macro Telegram services. |
| `README.md` | Describes KIS, paper/live modes, sync endpoints, API keys, and broker tests. | Must be rewritten after code decisions, not in analysis task. | Root documentation only; no runtime import. |

## Stop Decision

`review_required` is not empty. Per Task 002, this is not a test failure, but it
does block Task 003 and all subsequent deletion tasks. The next safe action is
an owner decision for:

1. whether read-only KIS market-data adapters are removed or kept as disabled
   fixture-only contracts;
2. how `paper` and `live` modes should be represented after simplification;
3. whether `api/features/orders/**` is removed or replaced by `RebalancePlan`;
4. whether Telegram/reporting delivery scripts are removed or kept outside the
   supported test suite;
5. how UI pages should degrade when account sync and order drafts are removed.

Until those decisions are made, no live integration files should be deleted.
