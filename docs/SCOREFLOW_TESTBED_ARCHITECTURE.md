# Scoreflow Testbed Architecture

## Current Implemented Flow

The implemented score-flow testbed adds opt-in infrastructure around the existing TripleA strategy. Existing macro, allocation, risk budget, sector tilt, backtest, and order draft behavior remains backward-compatible by default.

Implemented flow:

```text
Data contracts
-> Testbed schema
-> Data snapshot and quality metadata
-> Common score contract
-> Observation universe and sector taxonomy
-> Common sector score
-> Specialized indicator plugins
-> Aggregated sector score
-> Sector allocation pressure
-> Macro distribution and state features
-> Regime response and adaptive offsets
-> Optional offset integration
-> Optional decision and score logging
-> Judgment evaluation and optimization metadata
```

## Explicit Non-Goals

- No live automatic execution.
- No return-only optimization.
- No permanent sector hierarchy.
- No bottleneck-as-universal-model.
- No black-box ML in v1.
- No automatic production parameter promotion.
