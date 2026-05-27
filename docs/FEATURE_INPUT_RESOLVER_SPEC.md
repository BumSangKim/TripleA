# Feature Input Resolver Spec

## Purpose

The Feature Input Resolver prevents reusable feature calculators from directly importing or calling plugin implementations.

## Flow

```text
FeatureSpec
-> required_dataset_types
-> PluginRegistry candidates by dataset_type
-> priority / health / quality / available_at filtering
-> PluginDataset selection
-> FeatureCalculator input
```

## FeatureSpec Policy

Reusable feature specs must use:

```yaml
required_dataset_types:
  - market_price_daily
```

They must not use:

```yaml
required_plugins:
  - kis_price_plugin
```

`required_plugins` is allowed only for PluginSignalSpec, where source-native semantics are the reason for coupling.

## Resolver Policy

- Plugin priority is handled by the resolver.
- Non-executable plugin health states are excluded.
- `available_at` later than `decision_time` is excluded.
- Missing inputs return fallback reason codes instead of inventing data.
- Selected datasets retain plugin IDs only as trace metadata.

## Non-goals

This resolver skeleton does not execute plugins, calculate features, create scores, generate order candidates, or connect to allocation/rebalancing/execution.
