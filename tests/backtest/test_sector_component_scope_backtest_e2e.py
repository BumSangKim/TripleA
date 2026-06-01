from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from api.features.backtests.service import BacktestsService
from api.features.backtests.sector_component_config import parse_sector_component_backtest_config
from api.features.backtests.sector_component_portfolios import parse_sector_component_sector_portfolios
from api.features.backtests.sector_component_scope import SectorComponentScope
from api.features.backtests.sector_component_scope_runner import run_sector_component_scope_backtest


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "backtests" / "sector_component"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_KEYS = {"account_id", "accountId", "order", "orders", "order_candidate", "orderCandidate", "execution", "broker"}


class FakeRepo:
    def run_backtest(self, body): return body
    def list_runs(self, limit): return []
    def get_run(self, run_id): return {}
    def get_decisions(self, run_id): return []
    def get_positions(self, run_id): return []
    def get_trades(self, run_id): return []


class FixtureSectorComponentDataProvider:
    def __init__(self, observations: list[dict[str, Any]], returns: list[dict[str, Any]], regimes: list[dict[str, Any]]) -> None:
        self.observations = observations
        self.returns = returns
        self.regimes = regimes
        self.calls: list[str] = []

    def list_sector_component_observations(self, config):
        self.calls.append("observations")
        return self.observations

    def list_sector_component_returns(self, config):
        self.calls.append("returns")
        return self.returns

    def list_sector_component_regimes(self, config):
        self.calls.append("regimes")
        return self.regimes


def test_current_scope_fixture_runs_all_enabled_sectors_independently() -> None:
    config, observations, returns, regimes, portfolios = _fixtures()
    provider = FixtureSectorComponentDataProvider(observations, returns, regimes)
    service = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=provider,
        sector_component_scope_runner=run_sector_component_scope_backtest,
    )

    result = service.run_sector_component_scope_backtest(SectorComponentScope(mode="all"), config, portfolios)

    assert provider.calls == ["observations", "returns", "regimes"]
    assert result.sector_scope.mode == "all"
    assert result.semantics == "independent_enabled_sector_backtests"
    assert result.status == "REVIEW_REQUIRED"
    assert result.parameter_version == "sector_component_e2e_p1"
    assert result.model_version == "sector_component_e2e_m1"
    assert result.data_snapshot_id.startswith("sector-component-scope:all:all:")
    assert [row.sector_id for row in result.comparison_rows] == ["SEMICONDUCTOR", "POWER_GRID", "BATTERY"]
    assert [child.sector_id for child in result.sector_results] == ["SEMICONDUCTOR", "POWER_GRID", "BATTERY"]
    assert all(child.sector_id != "MULTI_SECTOR" for child in result.sector_results)
    assert "HISTORICAL_RETURN_MISSING" in result.reason_codes


def test_current_scope_fixture_prevents_future_data_leakage() -> None:
    config, observations, returns, regimes, portfolios = _fixtures()
    result = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=FixtureSectorComponentDataProvider(observations, returns, regimes),
        sector_component_scope_runner=run_sector_component_scope_backtest,
    ).run_sector_component_scope_backtest(SectorComponentScope(mode="all"), config, portfolios)
    semiconductor = next(child for child in result.sector_results if child.sector_id == "SEMICONDUCTOR")
    january_trade = [
        row
        for row in semiconductor.attribution_rows
        if row.as_of_date.isoformat() == "2026-01-31" and row.component_name == "trade"
    ][0]

    assert january_trade.score == 0.60
    assert january_trade.score != 0.99


def test_current_scope_fixture_output_has_comparison_rows_and_audit_metadata() -> None:
    config, observations, returns, regimes, portfolios = _fixtures()
    result = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=FixtureSectorComponentDataProvider(observations, returns, regimes),
        sector_component_scope_runner=run_sector_component_scope_backtest,
    ).run_sector_component_scope_backtest(SectorComponentScope(mode="all"), config, portfolios)

    for row in result.comparison_rows:
        assert row.display_name
        assert row.portfolio_id
        assert row.status in {"OK", "REVIEW_REQUIRED", "HOLD", "NO_ACTION", "RISK_REDUCE_ONLY"}
        assert row.observation_count >= 1
        assert row.reason_codes
    assert result.warnings
    assert result.reason_codes


def test_current_scope_fixture_has_no_account_order_execution_or_broker_fields() -> None:
    config, observations, returns, regimes, portfolios = _fixtures()
    result = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=FixtureSectorComponentDataProvider(observations, returns, regimes),
        sector_component_scope_runner=run_sector_component_scope_backtest,
    ).run_sector_component_scope_backtest(SectorComponentScope(mode="all"), config, portfolios)

    assert _find_forbidden_keys(result.to_dict()) == []


def _fixtures():
    config = parse_sector_component_backtest_config(_load_yaml(FIXTURE_DIR / "sector_component_backtest_config.yaml"))
    observations = _load_json(FIXTURE_DIR / "current_scope_raw_component_observations.json")
    returns = _load_json(FIXTURE_DIR / "current_scope_historical_returns.json")
    regimes = _load_json(FIXTURE_DIR / "current_scope_macro_regime_records.json")
    portfolios = parse_sector_component_sector_portfolios(
        _load_yaml(FIXTURE_DIR / "current_scope_sector_portfolios.yaml"),
        taxonomy_raw=_load_yaml(PROJECT_ROOT / "config" / "sector_taxonomy.yaml"),
        investment_universe_raw={
            "universes": {
                "test": {
                    "assets": [
                        {"asset_code": "SMH"},
                        {"asset_code": "SOXX"},
                        {"asset_code": "XLU"},
                        {"asset_code": "LIT"},
                    ]
                }
            }
        },
    )
    return config, observations, returns, regimes, portfolios


def _load_json(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_KEYS:
                matches.append(child_path)
            matches.extend(_find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_find_forbidden_keys(child, f"{path}[{index}]"))
    return matches
