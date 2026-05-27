# Backtest Optimization Testbed Spec

## Judgment Before Return

The testbed evaluates realized regime judgment before portfolio return. Future windows are allowed only in evaluation modules such as `api/backtest_judgment`.

## Recursive Optimization

`api/optimization/` implements deterministic candidate generation, objective scoring, candidate persistence, robustness helpers, failure analysis, and reporting.

Objective priority:

1. Judgment quality
2. Survival
3. Robustness
4. Cost discipline
5. Return

Return cannot dominate the objective.

## Parameter Safety

Parameter sets can be stored and associated with optimization candidates, but no automatic production promotion exists.

## Backtest Integration

`BacktestRunRequest` includes optional testbed fields:

- `enableScoreflowTestbed`
- `enableDecisionLogging`
- `parameterSetId`
- `optimizationRunId`
- `initialSeedPolicy`

Defaults preserve existing behavior.
