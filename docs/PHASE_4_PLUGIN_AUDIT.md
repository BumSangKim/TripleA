# Phase 4 Existing Plugin Architecture Audit

## 1. Current Plugin-related Files And Modules

| Area | Paths | Current role |
|---|---|---|
| Data providers | `api/data/providers.py`, `api/data/models.py`, `api/data/source_registry.py`, `config/data_sources.yml` | Raw data provider contracts, mock providers, source metadata, and fallback policy metadata. |
| Specialized indicator plugins | `api/strategy/indicator_plugins/base.py`, `api/strategy/indicator_plugins/registry.py`, `api/strategy/indicator_plugins/bottleneck_plugin.py` | Strategy-side plugin scoring abstraction from the score-flow testbed. |
| Bottleneck data and engine | `api/bottleneck_data_service.py`, `api/trade_data_service.py`, `api/strategy/bottleneck_sector_engine.py` | Existing bottleneck-specific data and score-like sector output. |
| Testbed storage | `api/testbed/schema.py`, `api/testbed/snapshot_service.py` | Snapshot, feature, score, decision, and optimization tables for opt-in testbed infrastructure. |
| Configuration/docs/tests | `config/indicators.yaml`, `docs/SECTOR_INDICATOR_PLUGIN_SPEC.md`, `docs/SCOREFLOW_TESTBED_ARCHITECTURE.md`, `tests/test_indicator_plugin_registry.py`, `tests/test_bottleneck_plugin.py` | Existing plugin and score-flow references. |

No `api/data/plugins/`, `api/providers/`, `api/services/`, `api/collectors/`, `config/providers*.yml`, or `config/plugins*.yml` plugin directories exist in the current tree.

## 2. Plugin Registry Existence

`api/strategy/indicator_plugins/registry.py` defines `IndicatorPluginRegistry`. It registers `SpecializedIndicatorPlugin` implementations and returns `PluginScore` results for sectors.

There is no separate data-plugin registry yet. `api/data/source_registry.py` loads source configurations, but it resolves executable data sources rather than plugin contracts.

## 3. Plugin Base Interface Existence

`api/strategy/indicator_plugins/base.py` defines:

- `PluginScore`
- `SpecializedIndicatorPlugin`
- `fallback_plugin_score`

This is a score-flow testbed plugin interface, not the Phase 4 data-plugin contract. It is useful audit evidence, but should not be reused as the canonical PluginDataset contract because it already returns normalized score-like values.

`api/data/providers.py` defines `DataProvider`, which is closer to raw provider access than to a plugin output contract.

## 4. Plugin Output Shape

Current plugin output categories:

| Output | Location | Classification |
|---|---|---|
| `PriceBar`, `CurrentQuote`, `MacroObservation` | `api/data/models.py` | Raw provider response / raw normalized data. |
| `DataQualityCheck` | `api/data/models.py`, `api/data/quality.py` | Quality metadata near PluginQualityScore, but not plugin-scoped yet. |
| `PluginScore` | `api/strategy/indicator_plugins/base.py` | Score-like plugin output from the score-flow testbed. |
| Bottleneck sector results | `api/strategy/bottleneck_sector_engine.py` | Feature-like and score-like values coupled to a specific domain engine. |

## 5. Fallback Structure Existence

Existing fallback mechanisms:

- `api/data/source_registry.py` defines fallback policies such as `review_required`, `use_conservative_fallback`, and `risk_reduce_only`.
- `api/data/quality.py` normalizes fallback policy based on quality score.
- `api/strategy/indicator_plugins/base.py` provides `fallback_plugin_score`.
- `api/strategy/indicator_plugins/registry.py` catches plugin exceptions and returns fallback plugin scores.

Phase 4 should preserve these but avoid treating quality/fallback metadata as investment scores.

## 6. Time Metadata Audit

| Output | `as_of_date` | `available_at` | `retrieved_at` / updated time |
|---|---:|---:|---:|
| `PriceBar` | yes | no | `updated_at` |
| `CurrentQuote` | yes | no | `quote_time`, `updated_at` |
| `MacroObservation` | yes | no | `release_date`, `updated_at` |
| `DataQualityCheck` | yes | no | `updated_at` |
| `PluginScore` | yes | no | no |
| `data_snapshots` table | yes | no explicit `available_at` | `data_cutoff_at`, `created_at` |

`available_at` is not consistently represented yet. Phase 4 should add this to new contracts rather than retroactively rewriting existing providers.

## 7. Quality Metadata Audit

Quality metadata exists as:

- `DataQualityCheck.quality_score`, `missing_ratio`, `is_stale`, `warnings`, `fallback_policy`.
- `PluginScore.confidence`, `data_quality`, and `coverage`.
- `data_snapshots.quality_json` and `feature_store.quality_json`.

The current quality metadata mixes data quality and plugin score confidence in some score-flow paths. Phase 4 should separate PluginQualityScore / PluginHealthStatus from investment scoring.

## 8. Existing Feature / Plugin Coupling

| Coupling | Files | Assessment |
|---|---|---|
| Bottleneck plugin wraps `BottleneckSectorEngine` directly | `api/strategy/indicator_plugins/bottleneck_plugin.py`, `api/strategy/bottleneck_sector_engine.py` | High-coupling domain exception already exists. Phase 4 should model this as PluginSignal or explicitly declared high-coupling policy, not a generic reusable feature calculator. |
| Plugin registry returns `PluginScore` to sector aggregation | `api/strategy/indicator_plugins/registry.py`, `api/strategy/sector_score_aggregator.py` | Existing score-flow testbed behavior. Preserve for compatibility, but do not use as Phase 4 FeatureValue contract. |
| Feature store has generic `feature_value` column | `api/testbed/schema.py` | Close to FeatureValue storage, but lacks full Phase 4 metadata such as `available_at`, plugin dataset lineage, and dataset_type resolver semantics. |

## 9. Recommended Phase 4 Contract Insertion Points

- Add new Phase 4 contracts under a new neutral package such as `api/plugin_boundary/` or `api/features/`.
- Keep existing `api/strategy/indicator_plugins/` intact to preserve score-flow testbed behavior.
- Use adapter/reference tests to prove new reusable feature calculators depend on `dataset_type`, not concrete plugin classes.
- Add traceability storage in testbed-compatible tables or a small dedicated repository layer rather than rewriting existing provider tables.

## 10. Items Requiring User Decision Or Future Task Approval

- Whether existing `PluginScore` should be migrated, wrapped, or left as legacy score-flow testbed output in Phase 5.
- Whether bottleneck plugin output should become a `PluginSignal` adapter in a future compatibility task.
- Whether existing `feature_store` should be migrated to include `available_at` or whether Phase 4 should create a new boundary-specific table.
- Whether live provider output should be adapted to PluginDataset in-place or through a separate adapter layer.

## Classification Summary

| Classification | Current examples |
|---|---|
| Already close to PluginDataset | `PriceBar`, `CurrentQuote`, `MacroObservation` after adapter wrapping. |
| Raw provider response | `DataProvider` outputs and KIS/current-price provider paths. |
| Feature-like value emitted by plugin/engine | Bottleneck engine components such as trade/demand/supply/relative-strength components. |
| Score-like value emitted by plugin | `PluginScore.score`, `PluginScore.confidence`, sector aggregation inputs. |
| Account/broker constraint input | Account constraint modules and KIS sync data are separate and should not be absorbed into feature/plugin contracts. |
