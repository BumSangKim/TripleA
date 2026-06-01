# TripleA

TripleA is a local, deterministic investment decision and backtest workspace.
The current simplified architecture keeps score-flow, hard-constraint,
allocation, rebalancing, backtest, and audit/report contracts, while removing
real-account and broker-linked behavior.

## Current Architecture

The supported runtime is simulation-only:

```text
fixture/local data
-> validation and data quality metadata
-> feature values
-> score flow
-> macro / sector / risk / allocation / rebalancing logic
-> DecisionSnapshot / RebalancePlan / BacktestReport / AuditLog
```

The following are intentionally not part of the current architecture:

- broker adapters or brokerage API clients;
- account balance live synchronization;
- automatic order execution;
- order feature APIs or executable order drafts;
- external notification/reporting delivery;
- UI paper/live modes.

For the detailed simplification contract, see
`docs/simplification/SIMPLIFIED_ARCHITECTURE.md`.

## Development Rules

The canonical development guide is `MASTER_DEVELOPMENT_GUIDE.md`; coding-agent
operational rules are in `AGENTS.md`.

Core rules:

- No Threshold Switch.
- Use continuous Score Flow.
- Hard Constraints First.
- Backtest Before Execution.
- Explain Every Decision.
- Parameters are data, not hardcoded constants.
- Conservative fallback on uncertainty.
- No default automatic execution.

## Repository Layout

```text
api/
  core/                  FastAPI app factory, dependencies, error mapping
  domain/                Pure domain exceptions and contracts
  features/              Vertical-slice API features
  data/                  Local/raw data models, repositories, adapters
  score_pipeline/        Feature, score, quality, parameter, and audit contracts
  strategy/              Pure strategy/allocation logic
  backtest_engine.py     Local backtest engine
config/
  parameters/            Approved parameter data
  pipelines/             Pipeline manifest
  universe/              Asset master and selector config
docs/simplification/     Simplified architecture and test strategy
tests/
  architecture/          Import and boundary guardrails
  backtest/              Deterministic backtest tests
  code/                  Simplification contract tests
  integration/           Fixture-based integration checks
  unit/                  Unit-level contract tests
web/                     Local dashboard UI
```

## Supported Test Commands

```bash
git diff --check
pytest -q --collect-only
pytest tests/backtest -q
pytest tests/code -q
pytest tests/architecture -q
```

The broader deterministic suite may also be run with:

```bash
pytest tests/unit tests/integration -q
pytest tests -q
```

Supported tests must not require network access, real account state, local
secret files, broker credentials, or external notification services.
