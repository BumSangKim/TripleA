# Strategy SQLite Boundary Inventory

This document records the current `api/strategy/**` SQLite import baseline.
It is an inventory and guardrail only; it does not authorize new strategy-layer
database access.

## Scope

- Baseline command: `rg "import sqlite3|from sqlite3" api/strategy -n`
- Baseline test: `tests/architecture/test_strategy_sqlite_baseline.py`
- Current goal: prevent new SQLite imports in `api/strategy/**` while later
  tasks separate existing persistence and data access behind explicit ports.
- Production code changes in this task: none.

## Current Baseline

| File | Current sqlite purpose | Caller or composition point | Recommended target owner | Follow-up task | Remove now? |
|---|---|---|---|---|---|
| `api/strategy/common_sector_scoring_engine.py` | Reads `market_prices` history for common sector momentum, relative strength, volatility, and drawdown inputs. | `CommonSectorScoringEngine(conn).score_sector(...)` callers pass a SQLite connection directly. | Data Layer plus a sector price history port. | `TASK_STRATEGY_SQLITE_001_common_sector_price_history_port` | No. Requires a price history port and caller wiring. |
| `api/strategy/decision_logger.py` | Writes strategy decision audit rows into `strategy_decision_logs`. | Direct helper `log_strategy_decision(conn, ...)`. | Reporting / Audit repository. | `TASK_STRATEGY_SQLITE_002_decision_log_repository` | No. Requires audit repository boundary. |
| `api/strategy/macro_engine.py` | Holds a SQLite connection and calls root `api.macro_data_service.get_macro_snapshot(...)`. | `TripleAAllocator.allocate(...)` constructs `MacroEngine(self.conn)`. | Data Layer or Feature Layer macro snapshot reader port. | `TASK_STRATEGY_SQLITE_003_macro_snapshot_reader_port` | No. Requires macro snapshot port and allocator composition update. |
| `api/strategy/score_layer.py` | `SQLiteScoreStore` persists score runs and score values. | Optional `ScoreRunner(..., store=SQLiteScoreStore(conn))` composition. | Score Pipeline persistence or Reporting / Audit repository. | `TASK_STRATEGY_SQLITE_004_score_store_repository_boundary` | No. Store is a public integration point and needs compatible adapter extraction. |
| `api/strategy/score_store_service.py` | Writes per-entity score records into `score_store`. | Direct helper `store_score(conn, ...)`. | Score Pipeline persistence repository. | `TASK_STRATEGY_SQLITE_005_legacy_score_store_service_boundary` | No. Requires repository interface and migration path. |
| `api/strategy/triplea_allocator.py` | Accepts and passes SQLite connection for macro evaluation and sector asset mapping orchestration. | `TripleAAllocator(conn, ...)` and `TripleAAllocator.from_config(conn, ...)`. | Application composition/factory with explicit data ports. | `TASK_STRATEGY_SQLITE_006_allocator_composition_ports` | No. Requires staged port wiring without allocation behavior changes. |

## Notes

- `api/strategy/bottleneck_sector_engine.py` was removed from this baseline by
  `009A-lite`. It now consumes `TradeSnapshot` / `TradeSnapshotReader` instead
  of importing `api.trade_data_service` or `sqlite3`.
- This baseline is intentionally exact. If a later task removes SQLite from one
  of the listed files, shrink `SQLITE_IMPORT_BASELINE`. If a later task needs a
  new strategy persistence path, add a port/repository boundary instead of a new
  direct `sqlite3` import.
- No live execution, broker order submission, account execution, or order
  candidate behavior is involved in this inventory.

