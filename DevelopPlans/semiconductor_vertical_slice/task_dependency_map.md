# SEM-001 Semiconductor Task Dependency Map

```text
SEM-001 inventory and target contract
-> SEM-002 universe and canonical IDs
-> SEM-003 raw data and point-in-time contracts
-> SEM-004 normalization and smoothing
-> feature branches
   -> SEM-005 global demand
   -> SEM-006 AI CAPEX-token adapter
   -> SEM-007 memory price
   -> SEM-008 inventory and supply
   -> SEM-009 equipment and capacity
   -> SEM-010 earnings and quality
   -> SEM-011 market features
-> SEM-012 macro risk
-> SEM-013 subsector scoring
-> SEM-014 sector and asset scoring
-> SEM-015 MSCI World / ETF look-through
-> SEM-016 risk budget and active tilt
-> SEM-017 rebalancing and constraints
-> SEM-018 point-in-time backtest
-> SEM-019 validation gates
-> SEM-020 audit, reporting, and shadow handoff
-> SEM-999 final integration and status update
```

## Dependency rules

- SEM-002 and SEM-003 must complete before any new semiconductor feature uses
  an asset identifier or raw input.
- SEM-004 is required before SEM-005 through SEM-011 can share normalized
  feature outputs.
- SEM-005 through SEM-011 and SEM-012 are prerequisites for SEM-013.
- SEM-013 is required before sector/asset aggregation in SEM-014.
- SEM-015 is required before any active-tilt exposure proposal in SEM-016.
- SEM-016 and existing hard constraints are prerequisites for SEM-017.
- SEM-018 requires the completed diagnostic input-to-output chain; SEM-019
  requires its point-in-time backtest output; SEM-020 requires SEM-019 gates.
- No task in this map authorizes live execution, real-account mutation, or
  automatic production activation.

## Current blockers to carry forward

- No canonical MSCI World benchmark ID or point-in-time holdings source is in
  the current repository.
- Semiconductor-specific raw metric definitions and their source ownership are
  not yet defined.
- Any transition from diagnostic proposal to active allocation contribution is
  an owner-approved, backtest-gated decision and is not a dependency that this
  planning task may resolve.
