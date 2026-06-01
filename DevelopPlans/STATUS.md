# Development Status

## Current State

- Current phase: pre-execution score-flow foundation, modular monolith refactor checkpoint, strategy engine decoupling, legacy root data-service cleanup, and post-legacy gap resolution checkpoint are complete.
- Current task: none.
- Default execution posture: read-only analysis, backtest, score generation, review-only order candidates.
- Out of scope unless explicitly approved: live broker order submission, real-account mutation, automatic execution.

## Canonical Development Inputs

Read these before selecting or implementing the next task:

1. `MASTER_DEVELOPMENT_GUIDE.md`
2. `AGENTS.md`
3. `DevelopPlans/STATUS.md`

Area-specific references:

- Current structure inventory: `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
- Legacy cleanup inventory: `DevelopPlans/legacy_cleanup/current_legacy_cleanup_inventory.md`
- Strategy coupling inventory: `DevelopPlans/strategy_engine_decoupling/current_strategy_engine_coupling_inventory.md`
- Post-legacy gap inventory: `DevelopPlans/post_legacy_gap_resolution/current_gap_inventory.md`
- Root owner decision inventory: `DevelopPlans/post_legacy_gap_resolution/root_owner_decision_inventory.md`
- Score-flow gap plan: `DevelopPlans/post_legacy_gap_resolution/score_flow_gap_plan.md`

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
- Market data lookup defaults now enforce no-lookahead price/FX behavior.
- Backtest execution orchestration has a runner/service boundary; the backtests
  repository no longer imports strategy, root market data service, or market data
  collector modules directly.
- Intraday monitoring now has service/ports/schemas and router dependency
  wiring while remaining display/alert-ready only.

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

## Post-Legacy Gap Resolution Checkpoint

- Status: complete for tasks `001` through `015` from the post-legacy gap
  resolution task pack.
- Completed items:
  - evidence-based gap inventory created;
  - market data and backtest no-lookahead tests added and enforced;
  - backtests execution runner/service boundary added;
  - backtests repository orchestration imports removed;
  - repository strategy import expected xfail converted to a strict guardrail;
  - intraday service/ports/schemas added and router wired through service;
  - intraday raw DB fixture to API output regression added;
  - root owner decision inventory created;
  - score-flow migration gap plan created.
- Preserved boundaries:
  - no live execution, broker order submission, real-account mutation, or
    automatic trading behavior was added;
  - no strategy score formula, macro regime formula, allocation, rebalancing, or
    order-candidate behavior was intentionally changed;
  - root owner-unresolved files were documented only and not relocated.

## Current Product Baseline

- Score pipeline foundations are implemented.
- Backtest, feature, score, regime, sector, risk budget, allocation, rebalancing, reporting, and review-only order-candidate foundations exist.
- UI/API sync has been verified for main routes and mock-safe actions.
- Intraday monitoring exists as display/alert-ready persistence only.
- KIS/broker connectivity must remain read-only unless a future task explicitly approves execution behavior.

## Remaining Work

- Strategy SQLite/root data service extraction and macro/bottleneck legacy
  cleanup are complete; preserve the empty strategy SQLite baseline.
- One architecture test remains an expected xfail for known root owner-unresolved
  files.
- Phase 4 feature-layer work is not represented as formal task files in the current plan tree.
- Legacy/current engines for macro regime, sector tilt, risk budget, allocation, rebalancing, and order candidates remain partial relative to the master guide; see `DevelopPlans/post_legacy_gap_resolution/score_flow_gap_plan.md`.
- Root owner-unresolved files require owner-specific tasks before relocation; see `DevelopPlans/post_legacy_gap_resolution/root_owner_decision_inventory.md`.
- Real provider integrations should be added as read-only tasks first, with explicit env gates and tests.
- Order execution, real-account mutation, and automatic trading are not active development targets.

## Documentation Policy

- `docs/` has been intentionally removed, including API guide material.
- `MASTER_DEVELOPMENT_GUIDE.md` at the repository root is the canonical
  development guide.
- `AGENTS.md` is the short operational entrypoint that requires agents to read
  the root guide before modifying code, tests, config, prompts, or workflow
  docs.
- Do not recreate `docs/` as a parallel source of truth without explicit
  approval.

## Last Verified Commands

```bash
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/integration/pipeline -q
.venv/bin/python -m pytest tests/unit tests/integration -q
```

Last recorded result: architecture 50 passed and 1 xfailed; pipeline integration
22 passed; unit/integration 153 passed and 2 skipped.

## Next Recommended Task

Run one explicit execution unit only:

- `SFG-TASK-001` Macro Distribution Adapter from `DevelopPlans/post_legacy_gap_resolution/score_flow_gap_plan.md`, after owner confirmation, as adapter/contract work only with no allocation behavior activation.
