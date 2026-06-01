# Legacy Cleanup Completion

Status: complete as of 2026-06-01.

## Removed Files

The following root-level legacy data-service files were removed after their
behavior was moved to data-layer owners and covered by tests:

- `api/macro_data_service.py`
- `api/bottleneck_data_service.py`

## Canonical Owners

| Concern | Canonical owner | Adapter/composition path |
|---|---|---|
| Macro snapshot DB reads | `api/data/macro_snapshot_reader.py` | `api/data/strategy_data_readers.py` |
| Bottleneck snapshot DB reads | `api/data/bottleneck_snapshot_reader.py` | `api/data/strategy_data_readers.py` |
| Sector asset mapping DB reads | `api/data/bottleneck_snapshot_reader.py` | `api/data/strategy_data_readers.py` |

Strategy engines continue to depend on Protocol ports and domain input models.
Application composition injects the SQLite-backed readers.

## Active Root Files Kept

These root files remain intentionally out of scope for this cleanup pack:

- market data service and collector files: require a separate market-data owner
  decision.
- macro indicator collector: requires a separate ingestion owner decision.
- asset-universe helper, loader, mapping, schema, snapshot, and validator files:
  require a separate asset-universe owner decision.
- telegram/reporting helpers: require a separate notification/reporting owner
  decision.

No owner decision was invented for these files.

## Validation

Required checks:

```bash
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/integration/pipeline -q
.venv/bin/python -m pytest tests/unit tests/integration -q
rg -n "api\\.macro_data_service|macro_data_service" api tests scripts docs DevelopPlans
rg -n "api\\.bottleneck_data_service|bottleneck_data_service" api tests scripts docs DevelopPlans
```

Expected scan result: deleted root legacy names appear only in this historical
completion note.

## Execution Boundary

This cleanup did not add live execution, broker order submission,
real-account mutation, automatic order behavior, or KIS order behavior.

## Remaining Legacy Candidates

- Remaining root market-data files.
- Remaining root macro collection/reporting files.
- Remaining root asset-universe files.
- Existing architecture xfails for broader repository/strategy ownership work.

Each remaining candidate needs an explicit owner/relocation task before code is
changed.
