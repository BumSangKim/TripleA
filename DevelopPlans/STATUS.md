# Development Status

## Current State

- Current phase: pre-execution score-flow foundation, modular monolith refactor checkpoint, and strategy engine decoupling are complete.
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
- Strategy coupling inventory: `DevelopPlans/strategy_engine_decoupling/current_strategy_engine_coupling_inventory.md`
- Strategy decoupling completion: `docs/STRATEGY_ENGINE_DECOUPLING_COMPLETION.md`

## Active Architecture Baseline

- File-based investment decision manifest exists at `config/pipelines/investment_decision.yaml`.
- Pipeline manifest loading and validation live under `api/score_pipeline/pipeline_manifest.py`.
- Score persistence ownership is under `api/score_pipeline/score_store.py`.
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
  - macro snapshot reader port and SQLite adapter;
  - bottleneck snapshot reader port and SQLite adapter;
  - sector asset mapping reader port and SQLite adapter;
  - price history reader port and SQLite adapter;
  - decision log writer port and reporting repository;
  - score store persistence under score pipeline ownership;
  - deterministic raw-input-to-allocation-output integration test.
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

- Strategy SQLite/root data service extraction is complete; preserve the empty
  strategy SQLite baseline.
- Two architecture tests are expected xfails for known follow-up boundary work.
- Phase 4 feature-layer work is not represented as formal task files in the current plan tree.
- Legacy/current engines for macro regime, sector tilt, risk budget, allocation, rebalancing, and order candidates remain partial relative to the master guide.
- Real provider integrations should be added as read-only tasks first, with explicit env gates and tests.
- Order execution, real-account mutation, and automatic trading are not active development targets.

## Documentation Policy

- `docs/` keeps only current contracts, the development prompt, API reference material, and active boundary inventories.
- Completed task logs, inspection notes, final reports, validation reports, checklists, and one-off runbooks are not kept in `docs/`.
- `docs/README.md` is the documentation index.
- `docs/DEVELOPMENT_PROMPT.md` is the active Codex/LLM prompt.
- `AGENTS.md` is a short entrypoint that points agents to the canonical docs.

## Last Verified Commands

```bash
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/integration/pipeline -q
.venv/bin/python -m pytest tests/unit tests/integration -q
```

Last recorded result: architecture 43 passed and 2 xfailed; pipeline integration
16 passed; unit/integration 147 passed and 2 skipped.

## Next Recommended Task

Choose one explicit execution unit:

- Preserve the completed strategy engine decoupling boundary while continuing the next approved product or architecture task.
- Formalize the next Phase 4 feature-layer task.
- Harden read-only provider/data quality integration.
- Improve UI/API coverage for existing non-execution workflows.
