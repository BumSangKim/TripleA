# Development Status

## Current State

- Current phase: pre-execution score-flow foundation, modular monolith refactor checkpoint, strategy engine decoupling, legacy root data-service cleanup, post-legacy gap resolution checkpoint, layered score-flow feedback contract checkpoint, and AI Capex-Token adaptive shadow tuning checkpoint are complete.
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
- Layered score-flow feedback inventory:
  `DevelopPlans/layered_score_flow_feedback/current_layered_feedback_inventory.md`
- Layered score-flow feedback target contract:
  `DevelopPlans/layered_score_flow_feedback/target_architecture_contract.md`
- Layered score-flow feedback completion handoff:
  `DevelopPlans/layered_score_flow_feedback/completion.md`
- AI Capex-Token adaptive final validation summary:
  `reports/backtest/ai_capex_token_adaptive/final_validation_summary.md`

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
- Layered score-flow feedback contracts are present but non-activating:
  - `api/domain/decision_feedback.py`
  - `api/domain/decision_state.py`
  - `api/score_pipeline/feedback.py`
  - `api/score_pipeline/adapters/macro_distribution_adapter.py`
  - `api/score_pipeline/orchestrator_contracts.py`
  - `api/score_pipeline/orchestrator.py`

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

## Layered Score Flow Feedback Checkpoint

- Status: complete for tasks `001` through `011` from the layered score-flow
  feedback task pack.
- Completed boundaries:
  - current layered feedback inventory and target architecture contract;
  - `FeedbackSignal` domain contract;
  - `DecisionStateSnapshot` domain contract;
  - `FeedbackCollector` review-only collector;
  - `MacroDistributionAdapter` as non-activating `SFG-TASK-001` work;
  - orchestrator request/result contracts and non-activating
    `DecisionOrchestrator` skeleton;
  - raw SQLite macro input to feedback/output snapshot integration test;
  - layered feedback architecture guardrails.
- Preserved boundaries:
  - no allocation behavior activation;
  - no rebalancing or order-candidate behavior change;
  - no broker, KIS, live execution, real-account mutation, or automatic trading
    behavior;
  - no `docs/` recreation.

## AI Capex-Token Adaptive Shadow Tuning Checkpoint

- Status: complete for tasks `001` through `016` from the adaptive backtest
  tuning task pack.
- Completed artifacts:
  - current adaptiveness assessment;
  - adaptive scoring, normalization, memory-cycle, scenario distribution,
    sector diagnostic, penalty/turnover, and shadow-candidate contracts;
  - deterministic reports under `reports/backtest/ai_capex_token_adaptive/`;
  - selected shadow candidate config at
    `config/parameters/ai_capex_token_adaptive_selected_candidate.yaml`;
  - final validation summary at
    `reports/backtest/ai_capex_token_adaptive/final_validation_summary.md`.
- Final posture:
  - production remains disabled;
  - candidate is diagnostic/shadow only;
  - allocation contribution remains `0.0`;
  - no broker, live account, notification, or automatic trading behavior was
    added.
- Validation result:
  - full test suite: 1430 passed, 1 xfailed;
  - architecture: 70 passed, 1 xfailed;
  - backtest: 62 passed.

## Current Product Baseline

- Score pipeline foundations are implemented.
- Backtest, feature, score, regime, sector, risk budget, allocation, rebalancing, reporting, and review-only order-candidate foundations exist.
- UI/API sync has been verified for main routes and mock-safe actions.
- Intraday monitoring exists as display/alert-ready persistence only.
- KIS/broker connectivity must remain read-only unless a future task explicitly approves execution behavior.

## Semiconductor Vertical Slice Checkpoint

- Status: complete for `SEM-001` through `SEM-020` and `SEM-999`.
- The read-only `api/data` market snapshot boundary owns point-in-time asset
  price, currency, and FX input contracts. Missing eligible FX makes the
  base-currency feature unavailable with `REVIEW_REQUIRED`; no substitute rate
  or silent local-currency result is allowed.
- The completed slice is fixture-only and diagnostic/shadow-only. All score,
  tilt, rebalance, validation, and audit candidates remain non-activating;
  production is false and allocation contribution is `0.0`.
- Completion handoff: `DevelopPlans/semiconductor_vertical_slice/completion.md`.

## Remaining Work

- Strategy SQLite/root data service extraction and macro/bottleneck legacy
  cleanup are complete; preserve the empty strategy SQLite baseline.
- One architecture test remains an expected xfail for known root owner-unresolved
  files.
- Phase 4 feature-layer work is not represented as formal task files in the current plan tree.
- Legacy/current engines for macro regime, sector tilt, risk budget, allocation, rebalancing, and order candidates remain partial relative to the master guide; see `DevelopPlans/post_legacy_gap_resolution/score_flow_gap_plan.md`.
- Layered score-flow feedback foundation is contract/skeleton only. Activation
  requires owner confirmation plus backtest/walk-forward validation.
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
git diff --check
.venv/bin/python -m pytest -q --collect-only
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/code -q
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m pytest tests/integration -q
.venv/bin/python -m pytest tests/backtest -q
.venv/bin/python -m pytest tests -q
```

Last recorded result: collect-only 1527 tests collected; architecture
72 passed and 1 xfailed; code 9 passed; unit 300 passed; integration
79 passed; backtest 65 passed; full suite 1526 passed and 1 xfailed.

## Next Recommended Task

Add a read-only, environment-gated market/FX snapshot adapter with independent
historical fixture reconciliation, while preserving the Semiconductor slice's
shadow-only, no-execution posture.

Alternative work after owner confirmation:

- AI Capex-Token shadow observation expansion: add larger deterministic
  fixture coverage and independent validation windows while keeping production
  disabled and allocation contribution at `0.0`.
- Alternative score-flow task: `SFG-TASK-002` Fixed Bucket Shift Replacement
  Plan as design and characterization only; do not activate allocation
  behavior.
