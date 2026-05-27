# Project Terminology

This document records project-wide terms that must stay distinct across the data, feature, plugin, and score layers.

## Phase 4 Terms

| Term | Meaning | Layer |
|---|---|---|
| `PluginDataset` | Standard dataset emitted by a data plugin. | Data Plugin Layer |
| `PluginQualityScore` | Reliability or quality metadata for plugin output. It is not an investment score. | Data Plugin Layer |
| `PluginHealthStatus` | Plugin execution, error, delay, and fallback state. | Data Plugin Layer |
| `PluginSignal` | Plugin-native or source-native investment input that cannot be represented as a reusable FeatureValue without losing source meaning. | Plugin Signal Bridge |
| `FeatureValue` | Reusable measured value or intermediate variable calculated from standard datasets. | Feature Layer |
| `SignalScore` | Normalized score for investment judgment. | Score Layer, Phase 5+ |
| `FactorScore` | Score composed from multiple signals or features. | Score Layer, Phase 5+ |
| `DecisionScore` | Final score used in macro, sector, risk, allocation, or decision logic. | Score Layer, Phase 5+ |

## Prohibited Phase 4 Term

`FeatureScore` is prohibited for new Phase 4 code and documents except when naming it as a deprecated/prohibited term.

Reason:

```text
FeatureScore confuses FeatureValue, PluginSignal, PluginQualityScore, and SignalScore.
```

Use `FeatureValue` for measured feature outputs and reserve `SignalScore`, `FactorScore`, and `DecisionScore` for Phase 5 or later.

## Classification Rules

1. If the value describes plugin state or output reliability, classify it as PluginQualityScore or PluginHealthStatus.
2. If the value is a source-native investment input from a specific provider/plugin, classify it as PluginSignal.
3. If the value can be recalculated from a standard dataset without importing a plugin class, classify it as FeatureValue.
4. If the value is normalized for investment judgment, classify it as a Score Layer output and defer implementation to Phase 5 or later.
