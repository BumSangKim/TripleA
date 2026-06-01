# Strategy SQLite Boundary Inventory

Status: completed historical inventory.

`api/strategy/**` no longer imports `sqlite3` directly. The architecture guard
is `tests/architecture/test_strategy_sqlite_baseline.py`, whose baseline is now
empty.

Legacy root data-service cleanup is recorded in
`docs/LEGACY_CLEANUP_COMPLETION.md`.

## Completed Extractions

| Former coupling | Current owner | Current contract |
|---|---|---|
| Macro snapshot DB read | `api/data/macro_snapshot_reader.py` via `api/data/strategy_data_readers.py` | `MacroSnapshotReader` |
| Bottleneck snapshot DB read | `api/data/bottleneck_snapshot_reader.py` via `api/data/strategy_data_readers.py` | `BottleneckSnapshotReader` |
| Sector asset mapping DB read | `api/data/bottleneck_snapshot_reader.py` via `api/data/strategy_data_readers.py` | `SectorAssetMappingReader` |
| Common sector price history SQLite read | `api/data/strategy_data_readers.py` | `PriceHistoryReader` |
| Strategy decision log SQLite write | `api/reporting/strategy_decision_log_repository.py` | `StrategyDecisionLogWriter` |
| Score run/value SQLite persistence | `api/score_pipeline/score_store.py` | `StrategyScoreStore` |

## Guardrails

- Strategy code depends on domain inputs and Protocol ports, not concrete DB
  readers or repositories.
- Application composition points, such as backtest execution, explicitly inject
  SQLite-backed readers/writers.
- Remaining root data files are separate owner decisions and are not imported
  by `api/strategy/**`.
- This inventory is not authorization for new strategy-layer DB access.

## Validation

```bash
rg -n "(^|\s)(import sqlite3|from sqlite3)" api/strategy
.venv/bin/python -m pytest tests/architecture/test_strategy_sqlite_baseline.py -q
.venv/bin/python -m pytest tests/integration/pipeline/test_strategy_engine_decoupled_input_to_output.py -q
```

Expected result: no direct SQLite import matches in `api/strategy/**`; tests
pass.
