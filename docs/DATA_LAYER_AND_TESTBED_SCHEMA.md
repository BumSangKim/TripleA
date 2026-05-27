# Data Layer And Testbed Schema

## Separation

- Raw data remains separate from feature data.
- Feature data remains separate from score data.
- Score data remains separate from decision data.
- Experiment data is stored separately from production state.

## Contracts

`api/data_contracts.py` defines `RawDataPoint`, `FeatureDataPoint`, `ScoreDataPoint`, `DecisionDataPoint`, quality metadata, snapshot references, model references, parameter references, and experiment references.

## Tables

`api/testbed/schema.py` creates:

- `data_snapshots`
- `feature_store`
- `score_store`
- `strategy_decision_logs`
- `parameter_sets`
- `optimization_runs`
- `optimization_candidates`
- `decision_evaluations`

The schema is create-if-not-exists and is safe for temporary SQLite tests.
