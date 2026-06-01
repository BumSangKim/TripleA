# Root Owner Decision Inventory

Status: active decision inventory for root-level files that must not be moved,
renamed, or deleted without an explicit owner-specific task.

This inventory does not approve relocation. It records current references,
likely owner options, required tests, and stop conditions so future cleanup does
not silently change public behavior.

## Guardrail Policy

- `tests/architecture/test_modular_monolith_import_boundaries.py` owns the root
  allowlist and owner-unresolved guardrails.
- Every file in the owner-unresolved set must appear in this inventory.
- New root-level Python files should fail architecture tests unless they are
  deliberately added to the allowlist and documented here.
- Live execution, broker mutation, order submission, allocation, rebalancing,
  and strategy score behavior are out of scope for this inventory.

## Decision Table

| root_file | current_references | likely_owner_options | required_tests_before_relocation | stop_conditions | architecture_change_required |
|---|---|---|---|---|---|
| `api/asset_data_requirements.py` | Imported by asset-universe tests and `api/asset_universe_validator.py` | Asset universe config owner, data requirements config owner | `tests/test_asset_data_requirements.py`, `tests/test_asset_universe_validator.py`, asset-universe config tests, architecture tests | Data requirement business rules or config path ownership is unclear | yes |
| `api/asset_universe_loader.py` | Imported by asset-universe tests, account constraint config, asset data requirements, mapping, snapshot, validator | Asset universe data/config owner | asset-universe loader/mapping/snapshot/validator tests, account constraint tests, architecture tests | Public config path or account constraint dependency would change | yes |
| `api/asset_universe_mapping.py` | Imported by asset-universe mapping tests and asset-universe snapshot flow | Asset universe mapping/config owner | `tests/test_asset_universe_mapping.py`, snapshot tests, architecture tests | Mapping schema or config contract would change | yes |
| `api/asset_universe_schema.py` | Imported by account eligibility, asset-universe tests, loader, mapping, validator | Domain contract owner or asset universe schema owner | schema tests, account trade eligibility tests, loader/validator tests, architecture tests | Account eligibility semantics would change | yes |
| `api/asset_universe_snapshot.py` | Imported by asset-universe snapshot tests | Asset universe data snapshot/export owner | snapshot tests, config tests, architecture tests | Snapshot reproducibility or output path contract is unclear | yes |
| `api/asset_universe_validator.py` | Imported by data requirements tests, validator tests, snapshot flow | Asset universe validation/config owner | validator tests, data requirements tests, snapshot tests, architecture tests | Missing-rule fallback policy would need invention | yes |
| `api/macro_indicator_collector.py` | Imported by macro feature repository, indicator poller service, macro collector tests | Data collection owner or macro feature data adapter owner | macro collector tests, macro feature API tests, indicator poller tests, architecture tests | Provider/API behavior or scheduling ownership is unclear | yes |
| `api/macro_telegram_report.py` | Imported by macro feature repository, daily report script, macro telegram report tests | Reporting/alerts owner or macro reporting owner | macro telegram report tests, macro feature API tests, script smoke where available, architecture tests | Telegram/reporting delivery semantics would change | yes |
| `api/market_data_collector.py` | Imported by scripts, `api/backtest_engine.py`, market data collector tests, runner boundary tests | Market data feature owner, data collection owner, or backtest data adapter owner | market data collector tests, backtest API tests, no-lookahead tests, pipeline tests, architecture tests | Live provider behavior, fixture collection behavior, or backtest auto-collect behavior is unclear | yes |
| `api/market_data_service.py` | Imported by market data feature repository, scripts, `api/backtest_engine.py`, market data tests, no-lookahead tests | Market data feature owner or data service owner | market data service tests, no-lookahead tests, backtest engine/API tests, pipeline tests, architecture tests | Future-data leakage policy or market holiday behavior would change | yes |
| `api/telegram_service.py` | Imported by alerts service, macro router, macro telegram report, telegram/report tests | Alerts/notification owner or reporting owner | alert service tests, macro router tests, telegram service tests, macro telegram report tests, architecture tests | Secret/config handling or delivery behavior would change | yes |

## Current Decision

All files above remain `owner_unresolved`. The conservative next step is an
owner-specific task for one file group at a time, with tests that prove behavior
is preserved from input fixture through API/report output where applicable.
