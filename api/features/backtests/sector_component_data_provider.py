from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUTS_PATH = PROJECT_ROOT / "config" / "backtests" / "sector_component_backtest_inputs.yaml"


class FileSectorComponentBacktestDataProvider:
    """Read-only diagnostic inputs for sector component scoped backtests."""

    def __init__(self, path: str | Path = DEFAULT_INPUTS_PATH) -> None:
        self.path = Path(path)

    def list_sector_component_observations(self, config: Any) -> tuple[dict[str, Any], ...]:
        return tuple(_load_inputs(self.path).get("observations") or ())

    def list_sector_component_returns(self, config: Any) -> tuple[dict[str, Any], ...]:
        return tuple(_load_inputs(self.path).get("historical_returns") or ())

    def list_sector_component_regimes(self, config: Any) -> tuple[dict[str, Any], ...]:
        return tuple(_load_inputs(self.path).get("macro_regime_records") or ())


def _load_inputs(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("sector component backtest inputs must be a mapping")
    return raw
