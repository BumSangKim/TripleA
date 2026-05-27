# Sector Indicator Plugin Spec

## Common Score First

Every sector can receive a common score from price and market features. Specialized data is optional.

## Plugin Architecture

`api/strategy/indicator_plugins/` defines a `SpecializedIndicatorPlugin` protocol and registry. Plugins return normalized `PluginScore` values with confidence, data quality, coverage, components, reason codes, model version, and parameter version.

## Bottleneck Migration

`BottleneckIndicatorPlugin` wraps existing `BottleneckSectorEngine` behavior. It applies only to configured sectors and is not the universal sector model.

## Allocation Pressure

Sector score aggregation feeds `SectorAllocationPressure`. Pressure is continuous and does not create permanent core/satellite hierarchy or direct orders.
