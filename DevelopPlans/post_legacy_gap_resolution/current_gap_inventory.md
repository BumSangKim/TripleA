# Post-Legacy Gap Inventory

Status: active inventory for the post-legacy gap resolution batch.

This file records evidence-based follow-up work after strategy engine
decoupling and scoped root legacy cleanup. It is not approval to change
strategy behavior, relocate owner-unresolved root files, add live execution, or
recreate deleted documentation trees.

Canonical references for this inventory:

- `MASTER_DEVELOPMENT_GUIDE.md`
- `AGENTS.md`
- `DevelopPlans/STATUS.md`
- `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
- `DevelopPlans/legacy_cleanup/current_legacy_cleanup_inventory.md`

Note: earlier task prompts may reference the former documentation tree. The
current repository policy says the documentation tree was intentionally removed
and must not be recreated as a parallel source of truth without explicit
approval.

## GAP-001 Market Data No-Lookahead Risk

- `gap_id`: `GAP-001`
- `evidence_files`:
  - `api/market_data_service.py`
  - `DevelopPlans/STATUS.md`
  - `MASTER_DEVELOPMENT_GUIDE.md`
- `risk`: Price and FX point lookups can use a limited future-date fallback when
  no same-day or prior row exists. That can leak future data into backtests or
  downstream reporting.
- `why_now`: The master guide requires future-data leakage prevention, and this
  gap is a behavior-level risk before further backtest work.
- `allowed_next_step`: Add failing no-lookahead tests for price and FX lookup
  behavior, then harden the lookup path in a dedicated task.
- `blocked_change`: Do not invent new market-data business rules, provider
  behavior, or collection policy while recording this gap.
- `required_tests`:
  - `.venv/bin/python -m pytest tests/unit tests/integration -q`
  - targeted market-data no-lookahead tests added by the follow-up task

## GAP-002 Backtest Output No-Lookahead Risk

- `gap_id`: `GAP-002`
- `evidence_files`:
  - `api/backtest_engine.py`
  - `api/market_data_service.py`
  - `api/features/backtests/repository.py`
- `risk`: Backtest points, positions, trades, and persisted decisions may be
  affected if market-data lookup can select future price or FX rows.
- `why_now`: Backtest output is an observable product surface and should be
  guarded before expanding backtest functionality.
- `allowed_next_step`: Add regression coverage proving output dates are not
  sourced from future market data, then adjust the minimal lookup behavior
  needed to satisfy the test.
- `blocked_change`: Do not modify allocation, rebalancing, order-candidate,
  broker, or execution behavior.
- `required_tests`:
  - `.venv/bin/python -m pytest tests/integration/pipeline -q`
  - targeted backtest no-lookahead output tests added by the follow-up task

## GAP-003 Backtests Repository Boundary Debt

- `gap_id`: `GAP-003`
- `evidence_files`:
  - `api/features/backtests/repository.py`
  - `tests/architecture/test_modular_monolith_import_boundaries.py`
  - `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
- `risk`: The backtests repository owns persistence but also imports strategy,
  market-data collection, and runner composition. That keeps a known
  architecture test in expected-xfail state.
- `why_now`: Legacy cleanup is complete for the scoped root services, so the
  remaining expected xfail should be narrowed through an explicit boundary.
- `allowed_next_step`: Add architecture tests that make the desired repository
  boundary observable, then extract a small runner/service adapter without
  changing public API behavior.
- `blocked_change`: Do not rewrite the backtest engine, change route response
  shape, or change strategy allocation semantics.
- `required_tests`:
  - `.venv/bin/python -m pytest tests/architecture -q`
  - targeted backtests boundary tests added by the follow-up task

## GAP-004 Intraday Slice Boundary Exception

- `gap_id`: `GAP-004`
- `evidence_files`:
  - `api/features/intraday/router.py`
  - `api/features/intraday/__init__.py`
  - `api/features/intraday/repository.py`
  - `api/features/intraday/collector.py`
  - `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
- `risk`: The intraday router directly reaches the DB connection,
  repositories, config loading, and collection orchestration through the package
  facade. That makes the slice harder to test as a standard router/service
  boundary.
- `why_now`: Intraday events must remain display/alert-only, but the public API
  should still have deterministic input-to-output coverage and clear ownership.
- `allowed_next_step`: Add service, port, and schema contracts that preserve the
  current route behavior, then wire the router through that service.
- `blocked_change`: Do not connect intraday events to strategy score,
  allocation, rebalancing, order candidates, broker execution, or automatic
  trading.
- `required_tests`:
  - `.venv/bin/python -m pytest tests/architecture -q`
  - targeted intraday API regression tests added by the follow-up task

## GAP-005 Root Owner Unresolved Files

- `gap_id`: `GAP-005`
- `evidence_files`:
  - `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
  - `DevelopPlans/legacy_cleanup/current_legacy_cleanup_inventory.md`
  - `tests/architecture/test_modular_monolith_import_boundaries.py`
- `risk`: Several root-level files remain explicitly owner-unresolved or
  blocked from relocation. Moving or deleting them without owner decisions can
  break public APIs, data collection, or asset-universe contracts.
- `why_now`: The legacy cleanup pack intentionally excluded these files, so
  follow-up work should keep the TODOs visible instead of silently expanding
  cleanup scope.
- `allowed_next_step`: Document owner decisions and keep architecture xfail or
  allowlist entries scoped until an owner-specific migration task exists.
- `blocked_change`: Do not move, delete, or rename root market-data,
  macro-collector, reporting, telegram, or asset-universe files in this batch
  unless a later task explicitly narrows and tests that move.
- `required_tests`:
  - `.venv/bin/python -m pytest tests/architecture -q`

## GAP-006 Stale Reference Cleanup After Documentation Removal

- `gap_id`: `GAP-006`
- `evidence_files`:
  - `DevelopPlans/STATUS.md`
  - `DevelopPlans/refactor_modular_monolith/current_structure_inventory.md`
  - `DevelopPlans/legacy_cleanup/current_legacy_cleanup_inventory.md`
  - `MASTER_DEVELOPMENT_GUIDE.md`
- `risk`: Some historical inventories still describe former documentation
  paths as active references, while the current status and root guide state that
  the documentation tree was intentionally removed.
- `why_now`: Status and inventory files should point future Codex tasks at the
  current canonical inputs before more architecture work begins.
- `allowed_next_step`: Update status or inventory references only where they
  clarify scope and do not duplicate the root guide.
- `blocked_change`: Do not recreate deleted documentation or add a competing
  global status file.
- `required_tests`:
  - `git diff --check`
  - `test -f MASTER_DEVELOPMENT_GUIDE.md`
  - `test -f DevelopPlans/STATUS.md`

## GAP-007 Score-Flow Gap Plan Required

- `gap_id`: `GAP-007`
- `evidence_files`:
  - `MASTER_DEVELOPMENT_GUIDE.md`
  - `DevelopPlans/STATUS.md`
  - `api/strategy/macro_engine.py`
  - `api/strategy/triplea_allocator.py`
- `risk`: Existing macro regime labeling and fixed bucket shifts remain partial
  relative to the continuous score-flow principles in the root guide.
- `why_now`: This affects investment behavior, so it needs an explicit plan and
  approval point before code changes.
- `allowed_next_step`: Document the gap and propose a future score-flow
  migration plan with approval gates.
- `blocked_change`: Do not change macro regime thresholds, score formulas,
  sector tilt, risk budget, allocation targets, rebalancing, order-candidate
  behavior, or execution behavior in this batch.
- `required_tests`:
  - planning/status validation only until an approved behavior task exists

## Current Expected Baseline

- Architecture tests are expected to pass with the existing known xfails.
- Strategy engine decoupling and scoped legacy cleanup are complete.
- Live execution, broker order submission, real-account mutation, and automatic
  trading remain out of scope.
