from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from api.features.backtests.service import BacktestsService
from api.features.backtests.sector_component_config import parse_sector_component_backtest_config
from api.features.backtests.sector_component_runner import run_sector_component_backtest


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "backtests" / "sector_component"


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

    def list_sector_component_observations(self, config):
        return self.observations

    def list_sector_component_returns(self, config):
        return self.returns

    def list_sector_component_regimes(self, config):
        return self.regimes


def test_sector_component_backtest_fixture_to_result_e2e() -> None:
    config, observations, returns, regimes = _fixtures()
    result = _run(config, observations, returns, regimes)

    assert result.status == "REVIEW_REQUIRED"
    assert result.sector_id == "MULTI_SECTOR"
    assert result.parameter_version == "sector_component_e2e_p1"
    assert result.model_version == "sector_component_e2e_m1"
    assert result.data_snapshot_id.startswith("sector-component-backtest:MULTI_SECTOR")
    assert result.metric_summaries[0].observation_count == 5
    assert result.attribution_rows
    assert result.sensitivity_results
    assert result.regime_breakdowns
    assert {"SEMICONDUCTOR", "HEALTHCARE"} <= {row.sector_id for row in result.attribution_rows}


def test_sector_component_backtest_blocks_future_data_leakage() -> None:
    config, observations, returns, regimes = _fixtures()
    result = _run(config, observations, returns, regimes)
    january_trade = [
        row
        for row in result.attribution_rows
        if row.sector_id == "SEMICONDUCTOR"
        and row.as_of_date.isoformat() == "2026-01-31"
        and row.component_name == "trade"
    ][0]

    assert january_trade.score == 0.60
    assert january_trade.data_snapshot_id == "sector-component:SEMICONDUCTOR:2026-01-31:sector_component_e2e_p1"


def test_sector_component_backtest_is_reproducible_from_fixed_input() -> None:
    config, observations, returns, regimes = _fixtures()
    first = _run(config, observations, returns, regimes)
    second = _run(config, list(reversed(observations)), list(reversed(returns)), list(reversed(regimes)))

    assert first.to_dict() == second.to_dict()


def test_sector_component_backtest_conservative_fallbacks_are_reported() -> None:
    config, observations, returns, regimes = _fixtures()
    result = _run(config, observations, returns, regimes)
    warning_codes = {warning.code for warning in result.warnings}

    assert "COMPONENT_REQUIRED_INPUT_MISSING" in warning_codes
    assert "HISTORICAL_RETURN_MISSING" in warning_codes
    assert "SECTOR_COMPONENT_LOW_DATA_QUALITY" in warning_codes
    assert "REVIEW_REQUIRED" in result.reason_codes


def test_sector_component_backtest_result_field_completeness() -> None:
    config, observations, returns, regimes = _fixtures()
    result = _run(config, observations, returns, regimes)
    payload = result.to_dict()

    assert payload["metric_summaries"]
    assert payload["attribution_rows"]
    assert payload["sensitivity_results"]
    assert payload["regime_breakdowns"]
    assert payload["warnings"]
    assert payload["parameter_version"] == "sector_component_e2e_p1"
    assert payload["model_version"] == "sector_component_e2e_m1"
    assert "data_snapshot_id" in payload


def test_sector_component_backtest_has_no_account_order_or_execution_output() -> None:
    config, observations, returns, regimes = _fixtures()
    payload = _run(config, observations, returns, regimes).to_dict()
    forbidden_keys = {"account_id", "order", "orders", "order_candidate", "execution", "broker"}

    assert forbidden_keys.isdisjoint(payload)
    assert all(forbidden_keys.isdisjoint(row) for row in payload["attribution_rows"])
    assert all(forbidden_keys.isdisjoint(summary) for summary in payload["metric_summaries"])


def _run(config, observations, returns, regimes):
    service = BacktestsService(
        FakeRepo(),
        sector_component_data_provider=FixtureSectorComponentDataProvider(observations, returns, regimes),
        sector_component_runner=run_sector_component_backtest,
    )
    return service.run_sector_component_backtest(config)


def _fixtures():
    config = parse_sector_component_backtest_config(_load_yaml("sector_component_backtest_config.yaml"))
    observations = _load_json("raw_component_observations.json")
    returns = _load_json("historical_returns.json")
    regimes = _load_json("macro_regime_records.json")
    return config, observations, returns, regimes


def _load_json(filename: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURE_DIR / filename).read_text(encoding="utf-8"))


def _load_yaml(filename: str) -> dict[str, Any]:
    return yaml.safe_load((FIXTURE_DIR / filename).read_text(encoding="utf-8"))
