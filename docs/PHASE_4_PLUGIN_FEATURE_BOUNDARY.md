# Phase 4 Plugin / Feature / Signal Boundary

## 1. Phase 4 Purpose

Phase 4 is redefined as the Plugin / Feature / Signal Boundary phase.

The goal is not to implement many feature calculators. The goal is to define the minimum contracts and layer boundaries needed for plugin-shaped data to flow into later feature and score work without direct implementation coupling.

## 2. Phase 4 Non-goals

Phase 4 does not implement:

- SignalScore, FactorScore, or DecisionScore calculations.
- Macro regime decisions.
- Sector attractiveness scoring.
- Risk budget calculations.
- Allocation target weights.
- Rebalancing intensity.
- Order candidate generation.
- Automatic order execution.
- Direct buy/sell decisions from a plugin result.

Hard constraints must remain hard constraints. They must not be weakened into features or scores.

## 3. Responsibility Separation

| Layer / Object | Responsibility |
|---|---|
| Data Plugin | Collect or derive source-specific datasets and plugin-native metadata. |
| PluginDataset | Contract object emitted by a plugin for feature input. |
| PluginQualityScore | Data/plugin reliability metadata only; not an investment score. |
| PluginHealthStatus | Operational health and fallback status for a plugin. |
| FeatureValue | A measured value or intermediate variable used by later scoring layers. |
| PluginSignal | Explicit exception for plugin-native or source-native investment inputs. |
| Score Layer | Phase 5+ layer that converts features/signals into comparable investment scores. |

## 4. Contract-based Loose Coupling

Phase 4 does not enforce full independence between every component. It enforces contract-based independence:

- reusable feature calculators must not depend on specific plugin implementations;
- data plugins emit PluginDataset, PluginQualityScore, and optionally PluginSignal;
- FeatureValue is not a score;
- PluginSignal is allowed only for plugin-native or source-native signals;
- SignalScore, FactorScore, and DecisionScore belong to Phase 5 or later.

This means direct imports from reusable feature calculators to concrete plugin classes are prohibited. Feature calculators depend on `dataset_type` and contract fields, not on `plugin_id` or plugin internals.

## 5. Prohibited Terminology

Do not introduce a feature-score concept in Phase 4.

The term `FeatureScore` is prohibited because it blurs four separate concepts: FeatureValue, PluginSignal, PluginQualityScore, and SignalScore. Phase 4 code and docs must use the precise term for the layer involved.

Allowed terms:

- `FeatureValue`
- `PluginQualityScore`
- `PluginHealthStatus`
- `PluginSignal`

Reserved for Phase 5 or later:

- `SignalScore`
- `FactorScore`
- `DecisionScore`

## 6. PluginQualityScore Versus PluginSignal

`PluginQualityScore` describes reliability, completeness, freshness, and operational confidence for plugin data. It can support fallback and confidence adjustment decisions, but it is not a buy/sell, attractiveness, regime, allocation, or rebalancing score.

`PluginSignal` is a formally declared exception for source-native or plugin-native investment inputs. Examples may include a provider-defined signal that cannot be faithfully represented as a generic raw dataset without losing source meaning. A PluginSignal still does not create orders or allocation changes in Phase 4.

## 7. FeatureValue Versus SignalScore

`FeatureValue` is a measured value or intermediate variable. It may carry units, as-of metadata, available-at metadata, provenance, and quality references.

`SignalScore` is a Phase 5+ score-layer output. It requires score-layer rules, normalization, confidence handling, explanation, and validation. Phase 4 only defines how data and feature contracts can safely reach that later layer.

## 8. Boundary Hand-off To Phase 5

Phase 4 hands off these artifacts to Phase 5:

- PluginDataset contract.
- PluginQualityScore and PluginHealthStatus contract.
- PluginSignal contract.
- FeatureValue contract.
- Dataset-type-based resolver policy.
- Point-in-time and `available_at` propagation rules.
- Coupling matrix for plugin-feature relationships.
- Mock plugin architecture tests proving the boundary.

Phase 5 may consume these contracts to build score-layer contracts and calculations. Phase 5 must not assume PluginQualityScore is an investment score and must treat PluginSignal as an explicit, auditable exception path.

## 9. Classification Rules

Use these questions to classify a value:

1. Is the value about plugin state, reliability, freshness, or quality?
   Use PluginQualityScore or PluginHealthStatus.
2. Is the value a native investment input emitted by a specific provider/plugin?
   Use PluginSignal.
3. Can the value be recomputed from a standard dataset without knowing the plugin class?
   Use FeatureValue.
4. Is the value normalized for investment judgment?
   It belongs to SignalScore, FactorScore, or DecisionScore in Phase 5 or later.

## 10. Registry And Resolver Boundary

Reusable FeatureCalculator implementations must receive PluginDataset inputs selected by a dataset-type resolver. They must not import concrete plugin classes or depend on plugin IDs.

The resolver architecture is documented in `docs/FEATURE_INPUT_RESOLVER_SPEC.md`.
