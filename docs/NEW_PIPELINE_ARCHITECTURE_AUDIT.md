# New Pipeline Architecture Audit

## 1. Current Repository Map

- `api/db.py`, `api/market_data_*`, `api/data/*`, and `api/telegram_service.py` are reusable infrastructure.
- `api/plugin_boundary/*`, `api/data_contracts.py`, and `api/testbed/*` provide useful contract and snapshot patterns.
- `api/strategy/*` contains mixed material: reusable small helpers and existing investment judgment logic.
- `api/backtest_engine.py` and `api/backtest_foundation.py` contain reusable historical simulation infrastructure, but current production allocator wiring must not be reused as the new strategy.
- `config/*` contains asset universe, data requirement, account constraint, score, risk, allocation, and profile config.
- `tests/*` contains guardrail, config, data, backtest, score, and account-constraint tests.

## 2. Reusable Infrastructure

- SQLite connection/table helpers in `api/db.py`.
- Read-only data collectors and market data repositories.
- Asset universe loaders, validators, and canonical mapping config.
- Account constraint contracts as a hard-gate reference.
- Telegram/reporting utilities where they do not create execution behavior.
- Test fixtures and pytest setup.

## 3. Legacy Strategy Logic Not To Migrate

The new pipeline must not copy or wrap these judgment paths:

- `api/strategy/triplea_allocator.py` fixed profile/macro-adjusted allocation path.
- `api/strategy/macro_engine.py` score-to-label logic.
- `api/strategy/risk_budget_engine.py` bucket clamp logic as investment policy.
- Existing sector tilt/offset logic if it directly implies allocation behavior.
- `api/services.py` order draft/approval paths as execution behavior.

The new implementation must not introduce `LegacyReferenceEngine`, `LegacyBridge`, golden-master comparison, or shadow compare code.

## 4. Candidate New Pipeline Module Locations

- `api/new_pipeline/contracts.py`
- `api/new_pipeline/parameters.py`
- `api/new_pipeline/data_quality.py`
- `api/new_pipeline/features.py`
- `api/new_pipeline/scoring.py`
- `api/new_pipeline/engines.py`
- `api/new_pipeline/backtest.py`
- `api/new_pipeline/audit.py`
- `config/parameters/default.yaml`
- `tests/test_new_pipeline_*.py`

This keeps new score-flow behavior separate from existing `api/strategy` judgment modules.

## 5. Existing Tests And Gaps

Existing tests cover asset universe, account constraints, data contracts, phase 5 score layer, phase 6-13 foundations, legacy/current backtest APIs, and live-execution guardrails. Gaps for the new pipeline are:

- End-to-end contract-only score-flow smoke test.
- Parameter valid-from/valid-to fallback tests.
- Feature plugin independence tests.
- Backtest leakage tests tied to parameter and snapshot availability.
- Order candidate review-only tests with `execution_allowed=false`.

## 6. Safety Risks

- Accidentally reusing current allocator, macro, or risk engines would reintroduce legacy judgment behavior.
- Data-quality fallback could increase risk if not explicitly bounded.
- Dominant regime labels could be misused as fixed allocation templates.
- Order candidates could be mistaken for executable broker orders unless explicitly non-executable.
- The requested docs `docs/PROJECT_CONTEXT.md`, `docs/PHASE_ROADMAP.md`, and `docs/CODEX_WORKFLOW.md` are absent. Related context was read from `docs/DEVELOPMENT_SEQUENCE_BACKTEST_FIRST.md`, `docs/STATUS.md`, and `DevelopPlans/STATUS.md`.

## 7. Recommended Implementation Sequence

1. Define serializable contracts and conservative enums.
2. Add versioned parameter registry and config.
3. Attach data-quality metadata and leakage guards to snapshots.
4. Build independent feature plugins.
5. Convert features to bounded scores.
6. Build macro, sector, risk, allocation, and rebalancing engines from score contracts.
7. Add backtest adapter and leakage tests.
8. Add audit logs and review-only order candidates.
9. Run full tests and safety-pattern scans before commit.

