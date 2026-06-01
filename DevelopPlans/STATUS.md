# Development Status

## Current State

- Current phase: pre-execution score-flow foundation, modular monolith refactor checkpoint, strategy engine decoupling, and legacy root data-service cleanup are complete.
- Current task: none.
- Default execution posture: read-only analysis, backtest, score generation, review-only order candidates.
- Out of scope unless explicitly approved: live broker order submission, real-account mutation, automatic execution.

## Canonical Development Inputs

Read these before selecting or implementing the next task:

1. `docs/DEVELOPMENT_PROMPT.md`
2. `docs/MASTER_DEVELOPMENT_GUIDE.md`
3. `docs/ARCHITECTURE_CONTRACT.md`
4. `docs/PIPELINE_MANIFEST_CONTRACT.md`
5. `DevelopPlans/STATUS.md`

Area-specific references:

- Backtest safety: `docs/BACKTEST_ENGINE_SPEC.md`
- Strategy SQLite extraction boundary: `docs/STRATEGY_SQLITE_BOUNDARY_INVENTORY.md`
- Current structure inventory: `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
- Legacy cleanup completion: `docs/LEGACY_CLEANUP_COMPLETION.md`
- Legacy cleanup inventory: `DevelopPlans/legacy_cleanup/current_legacy_cleanup_inventory.md`
- Strategy coupling inventory: `DevelopPlans/strategy_engine_decoupling/current_strategy_engine_coupling_inventory.md`
- Strategy decoupling completion: `docs/STRATEGY_ENGINE_DECOUPLING_COMPLETION.md`

## Active Architecture Baseline

- File-based investment decision manifest exists at `config/pipelines/investment_decision.yaml`.
- Pipeline manifest loading and validation live under `api/score_pipeline/pipeline_manifest.py`.
- Score persistence ownership is under `api/score_pipeline/score_store.py`.
- Macro snapshot reads are owned by `api/data/macro_snapshot_reader.py`.
- Bottleneck snapshot and sector asset mapping reads are owned by
  `api/data/bottleneck_snapshot_reader.py`.
- Trade data domain/port boundary exists under:
  - `api/domain/trade_data.py`
  - `api/strategy/trade_data_ports.py`
  - `api/features/market_data/trade_data_service.py`
- Architecture tests enforce layer boundaries under `tests/architecture/`.
- Pipeline integration tests enforce deterministic input-to-output behavior under `tests/integration/pipeline/`.
- Strategy engines now consume Protocol ports/domain inputs instead of direct
  SQLite/root data services.

## Strategy Engine Decoupling Checkpoint

- Status: complete.
- Completed tasks: `001` through `015` from the strategy engine decoupling task pack.
- Completed boundaries:
  - macro snapshot reader port, SQLite adapter, and data-layer owner;
  - bottleneck snapshot reader port, SQLite adapter, and data-layer owner;
  - sector asset mapping reader port, SQLite adapter, and data-layer owner;
  - price history reader port and SQLite adapter;
  - decision log writer port and reporting repository;
  - score store persistence under score pipeline ownership;
  - deterministic raw-input-to-allocation-output integration test.
- Legacy cleanup:
  - root macro snapshot service removed after data-layer owner migration;
  - root bottleneck snapshot and sector mapping service removed after
    data-layer owner migration;
  - stale refactor redirect documentation removed;
  - legacy removed input-to-output regression added.
- Guardrails:
  - `api/strategy/**` direct SQLite import baseline is empty.
  - `api/strategy/**` must not import root data services, DB modules,
    FastAPI/Starlette, or feature modules.
  - No live execution, broker order submission, real-account mutation, or
    automatic trading behavior was added.

## Current Product Baseline

- Score pipeline foundations are implemented.
- Backtest, feature, score, regime, sector, risk budget, allocation, rebalancing, reporting, and review-only order-candidate foundations exist.
- UI/API sync has been verified for main routes and mock-safe actions.
- Intraday monitoring exists as display/alert-ready persistence only.
- KIS/broker connectivity must remain read-only unless a future task explicitly approves execution behavior.

## Remaining Work

- Strategy SQLite/root data service extraction and macro/bottleneck legacy
  cleanup are complete; preserve the empty strategy SQLite baseline.
- Two architecture tests are expected xfails for known follow-up boundary work.
- Phase 4 feature-layer work is not represented as formal task files in the current plan tree.
- Legacy/current engines for macro regime, sector tilt, risk budget, allocation, rebalancing, and order candidates remain partial relative to the master guide.
- Real provider integrations should be added as read-only tasks first, with explicit env gates and tests.
- Order execution, real-account mutation, and automatic trading are not active development targets.

## Documentation Policy

- `docs/` keeps current contracts, boundary completion notes with ongoing
  guardrail value, API reference material, and active boundary inventories.
- Completed task logs, inspection notes, generic final reports, validation
  reports, checklists, and one-off runbooks are not kept in `docs/`.
- `docs/README.md` and `docs/DEVELOPMENT_PROMPT.md` are not present in the
  current working tree; use this status file and the active docs listed above
  until a documentation index is explicitly restored.
- `AGENTS.md` is a short entrypoint that points agents to the canonical docs.

## Last Verified Commands

```bash
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/integration/pipeline -q
.venv/bin/python -m pytest tests/unit tests/integration -q
```

Last recorded result: architecture 47 passed and 2 xfailed; pipeline integration
18 passed; unit/integration 149 passed and 2 skipped. Deleted legacy root
service names appear only in `docs/LEGACY_CLEANUP_COMPLETION.md` as historical
removal evidence.

## Next Recommended Task

Choose one explicit execution unit:

- Preserve the completed strategy engine decoupling and legacy cleanup boundaries while continuing the next approved product or architecture task.
- Formalize the next Phase 4 feature-layer task.
- Harden read-only provider/data quality integration.
- Improve UI/API coverage for existing non-execution workflows.
