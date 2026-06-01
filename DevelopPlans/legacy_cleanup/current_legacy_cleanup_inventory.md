# Legacy Cleanup Inventory

Status: inspection inventory only. This file records removable legacy
candidates after strategy engine decoupling. It does not authorize deletion by
itself.

## Scope

- Strategy engine decoupling is complete in `DevelopPlans/STATUS.md`.
- `api/strategy/**` does not directly import SQLite, root data services, DB
  modules, FastAPI/Starlette, or feature modules.
- This cleanup pack may evaluate root macro and bottleneck data services only.
- Market data collectors/services, macro collectors, and asset-universe root
  files require separate owner decisions and are not deletion targets here.

## Candidate Inventory

| candidate_path | candidate_type | current_references | required_tests_before_removal | removal_task_id | stop_condition |
|---|---|---|---|---|---|
| root macro snapshot service | `removed` | Replaced by `api/data/macro_snapshot_reader.py`; behavior covered by `tests/data/test_macro_snapshot_reader.py` | Keep behavior-preserving tests and import guardrails passing | `003`, `004` | Public API route or strategy engine requires the removed root path directly |
| root bottleneck snapshot and mapping service | `removed` | Replaced by `api/data/bottleneck_snapshot_reader.py`; behavior covered by `tests/data/test_bottleneck_snapshot_reader.py` | Keep behavior-preserving tests and import guardrails passing | `005`, `006` | Public API route or strategy engine requires the removed root path directly |
| historical refactor inventory redirect | `removed` | Historical redirect only; canonical inventory is `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md` | Link scan and architecture baseline | `007` | A current status or code path requires the historical redirect |
| `docs/refactor/STOP_CONDITIONS.md` | `active_keep` | Refactor guardrail reference under docs/refactor | No deletion in this cleanup pack | none | A later docs owner decides the file is obsolete |
| `docs/refactor/PER_TASK_CHECKLIST.md` | `active_keep` | Refactor workflow checklist under docs/refactor | No deletion in this cleanup pack | none | A later docs owner decides the file is obsolete |
| `docs/refactor/baseline_test_report.md` | `needs_owner_move` | Historical baseline report under docs/refactor | Leave in place pending docs retention decision | none | It is used as current test baseline evidence |
| `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md` | `active_keep` | Referenced by `DevelopPlans/STATUS.md`; records root owner inventory and unresolved owners | Keep as active refactor inventory unless a later task updates the canonical inventory | `008`, `010` | Removing it would erase the current owner-unresolved baseline |
| `docs/STRATEGY_SQLITE_BOUNDARY_INVENTORY.md` | `active_keep` | Referenced by `DevelopPlans/STATUS.md`; documents completed strategy SQLite/root data-service extraction boundary | Keep as boundary history/current guardrail reference; update only if task requires stale path cleanup | `010` | It starts competing with `DevelopPlans/STATUS.md` as task status |
| `docs/STRATEGY_ENGINE_DECOUPLING_COMPLETION.md` | `active_keep` | Referenced by `DevelopPlans/STATUS.md`; documents completed strategy decoupling and remaining root service risk | Keep as decoupling completion evidence; update historical references only when root legacy removal completes | `010` | It becomes stale after root legacy files are removed |
| `api/market_data_service.py` | `blocked` | Root market data service; explicitly excluded from this pack | Separate owner decision and read-only market-data migration task | none | This cleanup expands into market data service redesign |
| `api/market_data_collector.py` | `blocked` | Root collector; explicitly excluded from this pack | Separate data-collection owner decision | none | This cleanup expands into provider/collector behavior |
| `api/macro_indicator_collector.py` | `blocked` | Root collector; explicitly excluded from this pack | Separate macro data collection owner decision | none | This cleanup expands into macro ingestion behavior |
| `api/asset_data_requirements.py` | `blocked` | Root asset-universe helper in architecture allowlist | Separate asset-universe owner task | none | Business rules for universe metadata are needed |
| `api/asset_universe_loader.py` | `blocked` | Root asset-universe loader in architecture allowlist | Separate asset-universe owner task | none | Universe loader public usage is unclear |
| `api/asset_universe_mapping.py` | `blocked` | Root asset-universe mapping helper in architecture allowlist | Separate asset-universe owner task | none | Universe mapping owner is unresolved |
| `api/asset_universe_schema.py` | `blocked` | Root asset-universe schema in architecture allowlist | Separate asset-universe owner task | none | Schema relocation may affect config contracts |
| `api/asset_universe_snapshot.py` | `blocked` | Root asset-universe snapshot exporter in architecture allowlist | Separate asset-universe owner task | none | Snapshot reproducibility contract owner is unresolved |
| `api/asset_universe_validator.py` | `blocked` | Root asset-universe validator in architecture allowlist | Separate asset-universe owner task | none | Validator relocation may affect config tests |

## Observed Reference Scans

Macro root references currently appear in:

- `api/data/strategy_data_readers.py`
- `tests/test_macro_data_service.py` now imports the data-layer owner
- `tests/strategy/test_macro_engine_no_db_coupling.py`
- `tests/architecture/test_modular_monolith_import_boundaries.py`
- `docs/STRATEGY_ENGINE_DECOUPLING_COMPLETION.md`
- `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
- `DevelopPlans/strategy_engine_decoupling/current_strategy_engine_coupling_inventory.md`

Bottleneck root references currently appear in:

- `api/data/strategy_data_readers.py`
- `tests/test_trade_bottleneck_data_services.py` now imports the data-layer owner
- `tests/strategy/test_bottleneck_sector_engine_no_root_service.py`
- `tests/architecture/test_modular_monolith_import_boundaries.py`
- `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
- `DevelopPlans/strategy_engine_decoupling/current_strategy_engine_coupling_inventory.md`

## Required Cleanup Order

1. Add guardrail tests that make root legacy deletion observable.
2. Move macro snapshot read behavior into the data owner.
3. Root macro snapshot service removal is complete after behavior-preserving tests pass.
4. Move bottleneck snapshot and sector mapping read behavior into the data owner.
5. Root bottleneck snapshot and mapping service removal is complete after behavior-preserving tests pass.
6. Remove or scope stale historical docs and shrink root allowlists.
7. Add full input-to-output regression coverage and update status.

## Non-Goals

- No strategy scoring changes.
- No allocation, rebalancing, order, broker, KIS, or execution changes.
- No market data or asset-universe root service deletion in this pack.
