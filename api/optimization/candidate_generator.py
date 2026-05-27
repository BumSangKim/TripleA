from __future__ import annotations

import itertools


DEFAULT_GRID = {
    "macro_change_weight": [0.2, 0.4],
    "market_stress_weight": [0.3, 0.5],
    "adaptation_weight": [0.2],
    "portfolio_vulnerability_weight": [0.3],
    "max_risk_offset": [0.05],
    "max_speed_offset": [0.05],
    "max_friction_offset": [0.01],
    "sector_pressure_weight": [0.25],
    "plugin_score_weight": [0.25],
}


def generate_initial_candidates(limit: int = 8, grid: dict[str, list[float]] | None = None) -> list[dict]:
    grid = grid or DEFAULT_GRID
    keys = list(grid)
    candidates = [dict(zip(keys, values, strict=True)) for values in itertools.product(*[grid[key] for key in keys])]
    return candidates[:limit]
