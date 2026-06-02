# AI Capex-Token Tuning Execution Fixtures

These fixtures verify that the tuning execution loop is not a no-op.

They are synthetic, deterministic, diagnostic-only fixtures. They do not approve
production parameters, target weights, order candidates, broker behavior, or
execution behavior.

- `synthetic_two_memory_cycles.json`: explicit two-cycle snapshot payloads with
  S1/S3/S7-like diagnostic scenarios and a future-data leakage probe.
- `candidate_grid_smoke.json`: baseline plus three candidate parameter sets for
  output variation and no-op detection smoke tests.
