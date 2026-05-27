# Feature Traceability Spec

## Purpose

FeatureValue and PluginSignal outputs must remain reproducible and auditable. Storage must preserve source datasets, plugin/source metadata, versions, and point-in-time availability.

## FeatureValue Traceability

FeatureValue storage must preserve:

- `source_dataset_ids`
- `source_plugin_ids`
- `feature_version`
- `parameter_version`
- `calculation_method`
- `as_of_date`
- `available_at`
- `created_at`
- `reason_codes`
- `warnings`
- `metadata`

`source_plugin_ids` are trace metadata only. They must not become reusable feature calculation dependencies.

## PluginSignal Traceability

PluginSignal storage must preserve:

- `plugin_id`
- `provider`
- `source`
- `signal_version`
- `plugin_version`
- `source_dataset_ids`
- `source_native`
- `as_of_date`
- `available_at`
- `retrieved_at`
- `quality_score`
- `reason_codes`

## Storage Policy

- Raw/plugin datasets and FeatureValue rows are logically separate.
- FeatureValue rows trace back to PluginDataset IDs.
- PluginSignal rows explicitly preserve source-native status and plugin ID.
- Queries used for historical decisions must filter by `available_at <= decision_time`.
- Revised data must create a new row/version rather than overwrite old rows.

## Current Implementation

Phase 4 adds boundary-specific SQLite tables in `api/plugin_boundary/storage.py`:

- `plugin_boundary_feature_values`
- `plugin_boundary_plugin_signals`

These tables are intentionally separate from legacy score-flow `feature_store` and `score_store` tables.

## Non-goals

- No feature storage recalculates raw data.
- No latest data is exposed to past decision times.
- No source plugin ID is used as a reusable calculation dependency.
- No score, allocation, rebalancing, order, or execution behavior is added.
