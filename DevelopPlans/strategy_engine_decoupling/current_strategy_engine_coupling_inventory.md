# Current Strategy Engine Coupling Inventory

Task: `001_inspect_strategy_engine_coupling_inventory.md` through
`015_update_architecture_guardrails_docs_status.md`
Scope: completed strategy engine decoupling inventory
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
rg -n "(^|\s)(import sqlite3|from sqlite3)|api\.features|fastapi|starlette|api\.(market_data_service|trade_data_service|data|market_data_collector|macro_indicator_collector)" api/strategy
```

Current matches after completion:

```text
<none>
```

No `api/strategy/**` import of `sqlite3`, `api.db`, `api.features`, FastAPI,
Starlette, or root data services was found.

## Coupling Matrix

| File | Current coupling type | Current caller/composition | Target owner | Needed port | Follow-up task |
|---|---|---|---|---|---|
| `api/strategy/macro_engine.py` | resolved | `SqliteMacroSnapshotReader` is injected at composition points | data, application composition | `MacroSnapshotReader` | completed by tasks `005` and `006` |
| `api/strategy/bottleneck_sector_engine.py` | resolved | `SqliteBottleneckSnapshotReader` is injected at composition points | data, application composition | `BottleneckSnapshotReader` | completed by tasks `007` and `008` |
| `api/strategy/common_sector_scoring_engine.py` | resolved | price history is read through a supplied reader | market_data | `PriceHistoryReader` | completed by tasks `009` and `010` |
| `api/strategy/triplea_allocator.py` | resolved | allocator receives explicit macro/bottleneck/sector/trade readers | application composition, data | `MacroSnapshotReader`, `BottleneckSnapshotReader`, `SectorAssetMappingReader`, `TradeSnapshotReader` | completed by tasks `006`, `008`, and `014` |
| `api/strategy/decision_logger.py` | resolved | feature repositories inject reporting writer adapters | reporting/audit | `StrategyDecisionLogWriter` | completed by tasks `011` and `012` |
| `api/strategy/score_layer.py` | resolved | SQLite score store moved under score pipeline owner | score_pipeline persistence | `StrategyScoreStore` | completed by task `013` |

## Current Baseline Alignment

`tests/architecture/test_strategy_sqlite_baseline.py` now requires an empty
direct SQLite import baseline for `api/strategy/**`.

## STOP_RECOMMENDED

No stop is recommended. The strategy engine decoupling sequence is complete.
