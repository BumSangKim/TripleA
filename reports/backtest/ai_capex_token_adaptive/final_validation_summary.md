# AI Capex-Token Adaptive Tuning Final Validation

## Scope

- Task pack: `ai_capex_token_adaptive_backtest_tuning_tasks_v2`
- Completed tasks: `001` through `016`
- Runtime posture: simulation/local-fixture only
- Final candidate mode: diagnostic shadow only

## Final Gate Checklist

- Current scoring adaptiveness assessment exists:
  `docs/ai_capex_token/CURRENT_ADAPTIVE_SCORING_ASSESSMENT.md`
- Adaptive normalization tests pass.
- Input collection to score output integration tests pass.
- At least two memory cycles are proven in
  `reports/backtest/ai_capex_token_adaptive/baseline_report.json`.
- Leakage tests pass.
- Diagnostic baseline remains unchanged when AI Capex-Token contribution is
  zero.
- Static-value audit is present in
  `reports/backtest/ai_capex_token_adaptive/final_shadow_candidate_report.json`.
- No broker, live account, or automatic trading behavior was added.
- Production remains disabled in every generated artifact.
- Selected candidate is shadow/diagnostic only:
  `config/parameters/ai_capex_token_adaptive_selected_candidate.yaml`.
- Parameter metadata is versioned under `ai_capex_token_adaptive_tuning_v0` and
  `ai_capex_token_adaptive_shadow_v0`.
- Reports include reason-code metadata and data-lineage references.

## Validation Commands

```bash
git diff --check
.venv/bin/python -m pytest -q --collect-only
.venv/bin/python -m pytest tests/architecture -q
.venv/bin/python -m pytest tests/code -q
.venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m pytest tests/integration -q
.venv/bin/python -m pytest tests/backtest -q
.venv/bin/python -m pytest tests -q
```

## Results

- `git diff --check`: passed
- collect-only: 1431 tests collected
- `tests/architecture`: 70 passed, 1 xfailed
- `tests/code`: 9 passed
- `tests/unit`: 245 passed
- `tests/integration`: 45 passed
- `tests/backtest`: 62 passed
- `tests`: 1430 passed, 1 xfailed

## Artifacts

- `reports/backtest/ai_capex_token_adaptive/final_shadow_candidate_report.json`
- `reports/backtest/ai_capex_token_adaptive/final_shadow_candidate_report.md`
- `reports/backtest/ai_capex_token_adaptive/walk_forward_sensitivity_stress_report.json`
- `reports/backtest/ai_capex_token_adaptive/penalty_overlay_turnover_tuning_report.json`
- `reports/backtest/ai_capex_token_adaptive/sector_component_tuning_report.json`
- `reports/backtest/ai_capex_token_adaptive/normalization_smoothing_tuning_report.json`
- `config/parameters/ai_capex_token_adaptive_selected_candidate.yaml`

## Remaining Limits

- Candidate quality is diagnostic and shadow-only.
- Tax-adjusted metrics are explicitly unsupported in the current fixture.
- Allocation contribution remains `0.0`.
- Larger deterministic fixture coverage and independent validation windows are
  required before any future allocation contribution task.
