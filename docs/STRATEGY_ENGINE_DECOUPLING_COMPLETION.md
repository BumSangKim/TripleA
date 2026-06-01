# Strategy Engine Decoupling Completion

Status: complete as of 2026-06-01.

## Removed Coupling Points

- `api/strategy/macro_engine.py` no longer imports SQLite or root macro data
  services.
- `api/strategy/bottleneck_sector_engine.py` no longer imports root bottleneck
  data services or DB-backed adapters.
- `api/strategy/common_sector_scoring_engine.py` no longer reads
  `market_prices` directly.
- `api/strategy/decision_logger.py` no longer writes SQLite rows directly.
- `api/strategy/score_layer.py` no longer owns SQLite score persistence.
- `api/strategy/triplea_allocator.py` no longer imports SQLite or root data
  services.

## Current Owner / Port / Adapter Structure

| Concern | Strategy port | Concrete owner |
|---|---|---|
| Macro snapshot input | `MacroSnapshotReader` | `api/data/macro_snapshot_reader.py` via `api/data/strategy_data_readers.py` |
| Bottleneck snapshot input | `BottleneckSnapshotReader` | `api/data/strategy_data_readers.py` |
| Sector asset mappings | `SectorAssetMappingReader` | `api/data/strategy_data_readers.py` |
| Price history | `PriceHistoryReader` | `api/data/strategy_data_readers.py` |
| Decision log writes | `StrategyDecisionLogWriter` | `api/reporting/strategy_decision_log_repository.py` |
| Score persistence | `StrategyScoreStore` | `api/score_pipeline/score_store.py` |

Application composition points explicitly inject concrete SQLite readers and
writers. Strategy engines consume domain inputs and Protocol ports only.

## Validation

```bash
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/integration/pipeline -q
.venv/bin/python -m pytest tests/unit tests/integration -q
```

The integration coverage includes
`tests/integration/pipeline/test_strategy_engine_decoupled_input_to_output.py`,
which validates raw DB/config fixture input through strategy reader adapters and
`TripleAAllocator` output while checking future-data exclusion and
review-only/no-execution output shape.

## Remaining Risks

- Remaining root data service files are legacy/data-layer implementation
  details and should not be imported by strategy.
- Feature repositories still have known architecture xfails for broader
  repository/strategy ownership cleanup.
- This work did not add live execution, broker order submission, real-account
  mutation, or automatic order behavior.
