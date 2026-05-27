# Plugin / Feature Coupling Policy

## Purpose

Plugin and Feature layers are neither fully independent nor freely intermingled. New designs must choose a structure based on coupling strength and must document the reason.

## Coupling Score Matrix

Each dimension is scored from 0 to 2.

| Dimension | 0 points | 1 point | 2 points |
|---|---|---|---|
| Source dependency | Source independent | Some source differences | Specific source dependent |
| Schema dependency | Standard schema is enough | Adapter needed | Provider schema directly needed |
| Calculation portability | Fully reusable | Some modification needed | Not reusable |
| Timing dependency | Normal `available_at` enough | Release rule needed | Source-specific timing required |
| Semantic dependency | General feature meaning | Some source definition included | Source definition is the feature |
| Auditability | Externally recalculable | Partially recalculable | Plugin-internal output only |

## Score Interpretation

| Total score | Required structure |
|---:|---|
| 0-3 | `PluginDataset -> reusable FeatureCalculator -> FeatureValue` |
| 4-7 | `PluginDataset + Adapter/Resolver -> FeatureCalculator -> FeatureValue` |
| 8-12 | `PluginSignal` allowed |

## Example Classifications

| Candidate | Typical score | Structure | Notes |
|---|---:|---|---|
| `market.price_momentum_3m` | 0-3 | FeatureValue | Reusable from daily market price datasets. |
| `market.realized_volatility_20d` | 0-3 | FeatureValue | Reusable from standard OHLCV datasets. |
| `macro.export_yoy` | 4-7 | FeatureValue with release/timing adapter | Requires release and revision timing but remains calculable from standard macro/export series. |
| `supply_chain.bottleneck_pressure` | 4-12 | FeatureValue or PluginSignal | If derived from auditable series, use FeatureValue. If plugin-native model semantics define the value, use PluginSignal. |
| `news.sentiment` | 8-12 | PluginSignal | Usually source/model-native and not fully reproducible from standard datasets. |
| `broker.product_tradability` | 8-12 or ConstraintInput candidate | Broker/account/product rules may be hard constraints rather than features. Do not weaken constraints into FeatureValue. |
| `etf.constituent_freshness` | 4-12 | FeatureValue with timing adapter or PluginSignal | Depends on provider revision timing and constituent publication semantics. |

## Decision Principles

- Use FeatureValue for simple reusable calculations over standard datasets.
- Use PluginSignal when meaning is source-native, provider-native, or plugin-model-native.
- Use PluginQualityScore / PluginHealthStatus for plugin reliability, freshness, and operational status.
- Use account or broker constraint inputs for account/product eligibility and hard constraints.
- Do not use FeatureValue to represent buy/sell decisions, target weights, rebalancing intensity, or order candidates.

## Required Codex Handling

For any future plugin/feature design, Codex must document:

- Coupling score by dimension.
- Selected structure.
- Reason for selecting FeatureValue, adapter path, PluginSignal, or ConstraintInput candidate.
- Point-in-time fields used, especially `available_at`.
- Whether the output is reusable or source-native.

## Existing Repository Implications

- Existing `api/strategy/indicator_plugins/PluginScore` is score-flow testbed output and should not become the Phase 4 FeatureValue contract.
- `BottleneckIndicatorPlugin` is a high-coupling domain path. Future migration should either wrap auditable inputs as PluginDataset-derived FeatureValue or classify the native pressure output as PluginSignal.
- Data providers in `api/data/providers.py` are raw provider paths. They should feed PluginDataset adapters instead of being imported by reusable feature calculators.
