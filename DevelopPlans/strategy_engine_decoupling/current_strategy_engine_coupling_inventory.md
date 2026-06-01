# Current Strategy Engine Coupling Inventory

Task: `001_inspect_strategy_engine_coupling_inventory.md`  
Scope: inspection-only strategy engine decoupling inventory  
Updated: 2026-06-01

## Preconditions Read

- `AGENTS.md`
- `docs/DEVELOPMENT_PROMPT.md`
- `docs/MASTER_DEVELOPMENT_GUIDE.md`
- `docs/ARCHITECTURE_CONTRACT.md`
- `docs/STRATEGY_SQLITE_BOUNDARY_INVENTORY.md`
- `DevelopPlans/STATUS.md`
- `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
- `tests/architecture/test_strategy_sqlite_baseline.py`

The requested `docs/PROJECT_CONTEXT.md`, `docs/PHASE_ROADMAP.md`, and
`docs/CODEX_WORKFLOW.md` files are not present in the current working tree.

## Search Commands

```bash
rg -n "(^|\s)(import sqlite3|from sqlite3)|api\.features|fastapi|starlette|api\.(macro_data_service|market_data_service|trade_data_service|bottleneck_data_service|data|market_data_collector|macro_indicator_collector)" api/strategy
```

Current matches:

```text
api/strategy/bottleneck_sector_engine.py:6:from api.bottleneck_data_service import BottleneckIndicatorItem, get_bottleneck_snapshot
api/strategy/decision_logger.py:4:import sqlite3
api/strategy/score_layer.py:5:import sqlite3
api/strategy/common_sector_scoring_engine.py:3:import sqlite3
api/strategy/macro_engine.py:3:import sqlite3
api/strategy/macro_engine.py:7:from api.macro_data_service import MacroSnapshot, get_macro_snapshot
api/strategy/triplea_allocator.py:3:import sqlite3
api/strategy/triplea_allocator.py:7:from api.bottleneck_data_service import get_sector_asset_mappings
```

No `api/strategy/**` import of `api.features`, `fastapi`, or `starlette` was
found.

## Coupling Matrix

| File | Current coupling type | Current caller/composition | Target owner | Needed port | Follow-up task |
|---|---|---|---|---|---|
| `api/strategy/macro_engine.py` | DB read plus root service import via `sqlite3.Connection` and `api.macro_data_service.get_macro_snapshot` | `TripleAAllocator.allocate()` constructs `MacroEngine(self.conn)` | data, application composition | `MacroSnapshotReader` | `005_prepare_macro_engine_port_api.md`, `006_wire_macro_reader_and_remove_macro_sqlite_coupling.md` |
| `api/strategy/bottleneck_sector_engine.py` | Root data service import and connection leakage via `api.bottleneck_data_service.get_bottleneck_snapshot` | `TripleAAllocator._profile_weights()` constructs `BottleneckSectorEngine(self.conn, ...)`; tests construct engine directly | data, application composition | `BottleneckSnapshotReader` | `007_prepare_bottleneck_sector_engine_port_api.md`, `008_wire_bottleneck_and_sector_mapping_readers.md` |
| `api/strategy/common_sector_scoring_engine.py` | Direct DB read from `market_prices` through `sqlite3.Connection` | Tests and score paths construct `CommonSectorScoringEngine(conn)` directly | market_data | `SectorPriceHistoryReader` | `009_add_common_sector_price_history_port.md`, `010_wire_common_sector_price_reader.md` |
| `api/strategy/triplea_allocator.py` | Composition leakage through `sqlite3.Connection`; root data service import for sector asset mappings | `api/backtest_engine.py` and `api/features/backtests/repository.py` create `TripleAAllocator.from_config(conn, ...)`; tests construct allocator directly | application composition, data | `MacroSnapshotReader`, `BottleneckSnapshotReader`, `SectorAssetMappingReader`, existing `TradeSnapshotReader` | `006_wire_macro_reader_and_remove_macro_sqlite_coupling.md`, `008_wire_bottleneck_and_sector_mapping_readers.md`, `010_wire_common_sector_price_reader.md`, `014_add_full_input_to_output_strategy_decoupling_tests.md` |
| `api/strategy/decision_logger.py` | DB write and schema bootstrap through `sqlite3.Connection` plus `api.testbed.schema.ensure_testbed_tables` | `api/features/backtests/repository.py` imports and calls `log_strategy_decision` when decision logging is enabled | reporting/audit | `DecisionLogWriter` | `011_add_decision_log_writer_port_and_adapter.md`, `012_wire_decision_logger_to_writer.md` |
| `api/strategy/score_layer.py` | Persistence leakage through embedded SQLite score store | Score runner integrations may pass `SQLiteScoreStore(conn)`; score persistence also exists under `api/score_pipeline/score_store.py` | score_pipeline persistence | `ScoreStore` / score repository boundary | `013_extract_score_store_repository_boundary.md` |

## Current Baseline Alignment

`tests/architecture/test_strategy_sqlite_baseline.py` currently allows direct
SQLite imports in:

- `api/strategy/common_sector_scoring_engine.py`
- `api/strategy/decision_logger.py`
- `api/strategy/macro_engine.py`
- `api/strategy/score_layer.py`
- `api/strategy/triplea_allocator.py`

The task sequence is still aligned with the current code. Root service coupling
remains in `macro_engine.py`, `bottleneck_sector_engine.py`, and
`triplea_allocator.py`; later tasks explicitly target those paths.

## STOP_RECOMMENDED

No stop is recommended for the next task. The observed coupling points match
the intended decoupling sequence, with one important note: current code still
imports `api.bottleneck_data_service` from `api/strategy/bottleneck_sector_engine.py`,
so tasks `007` and `008` must treat bottleneck data as an active strategy-root
service coupling.

