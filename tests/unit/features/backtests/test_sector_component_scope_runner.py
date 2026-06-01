from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from api.features.backtests.sector_component_config import (
    SectorComponentBacktestConfig,
    SectorComponentWeightSet,
)
from api.features.backtests.sector_component_models import SectorComponentObservation
from api.features.backtests.sector_component_portfolios import (
    SectorComponentSectorPortfolio,
    SectorPortfolioAsset,
)
from api.features.backtests.sector_component_runner import (
    SectorComponentRegimeRecord,
    SectorComponentReturnRecord,
)
from api.features.backtests.sector_component_scope import SectorComponentScope
from api.features.backtests.sector_component_scope_runner import run_sector_component_scope_backtest


def config() -> SectorComponentBacktestConfig:
    return SectorComponentBacktestConfig(
        parameter_version="p1",
        model_version="m1",
        enabled_components=("trade", "demand"),
        component_weight_grid=(SectorComponentWeightSet("balanced", {"trade": 0.5, "demand": 0.5}),),
        rebalance_frequency="monthly",
        decision_lag_days=1,
        transaction_cost_bps=0.0,
        tax_assumption_enabled=False,
        stress_periods=(),
        required_metrics=("total_return",),
        fallback_policy="REVIEW_REQUIRED",
    )


def portfolios() -> tuple[SectorComponentSectorPortfolio, ...]:
    return (
        SectorComponentSectorPortfolio(
            sector_id="SEMICONDUCTOR",
            display_name="Semiconductor",
            portfolio_id="sector_semiconductor_current_v1",
            display_order=10,
            assets=(SectorPortfolioAsset("SMH", 0.5), SectorPortfolioAsset("SOXX", 0.5, "secondary_proxy")),
        ),
        SectorComponentSectorPortfolio(
            sector_id="POWER_GRID",
            display_name="Power Grid",
            portfolio_id="sector_power_grid_current_v1",
            display_order=20,
            assets=(SectorPortfolioAsset("XLU", 1.0),),
        ),
        SectorComponentSectorPortfolio(
            sector_id="BATTERY",
            display_name="Battery",
            portfolio_id="sector_battery_current_v1",
            display_order=30,
            assets=(SectorPortfolioAsset("LIT", 1.0),),
        ),
    )


def observation(sector: str, component: str, score: float, as_of: date) -> SectorComponentObservation:
    return SectorComponentObservation(
        sector_id=sector,
        component_name=component,
        score=score,
        as_of_date=as_of,
        available_at=datetime(2026, as_of.month, min(as_of.day, 28), 9, tzinfo=UTC),
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id=f"raw:{sector}:{component}:{as_of.isoformat()}",
    )


def observations() -> tuple[SectorComponentObservation, ...]:
    rows = []
    for sector, base in (("SEMICONDUCTOR", 0.6), ("POWER_GRID", 0.5), ("BATTERY", 0.4)):
        rows.extend(
            [
                observation(sector, "trade", base, date(2026, 1, 31)),
                observation(sector, "demand", base + 0.1, date(2026, 1, 31)),
                observation(sector, "trade", base + 0.05, date(2026, 2, 28)),
                observation(sector, "demand", base + 0.15, date(2026, 2, 28)),
            ]
        )
    return tuple(rows)


def returns(include_battery: bool = True) -> tuple[SectorComponentReturnRecord, ...]:
    rows = [
        SectorComponentReturnRecord("SEMICONDUCTOR", date(2026, 1, 31), 0.02),
        SectorComponentReturnRecord("SEMICONDUCTOR", date(2026, 2, 28), 0.01),
        SectorComponentReturnRecord("POWER_GRID", date(2026, 1, 31), -0.01),
        SectorComponentReturnRecord("POWER_GRID", date(2026, 2, 28), 0.01),
    ]
    if include_battery:
        rows.extend(
            [
                SectorComponentReturnRecord("BATTERY", date(2026, 1, 31), -0.02),
                SectorComponentReturnRecord("BATTERY", date(2026, 2, 28), 0.03),
            ]
        )
    return tuple(rows)


def regimes() -> tuple[SectorComponentRegimeRecord, ...]:
    return tuple(
        SectorComponentRegimeRecord(sector, as_of, "risk_on")
        for sector in ("SEMICONDUCTOR", "POWER_GRID", "BATTERY")
        for as_of in (date(2026, 1, 31), date(2026, 2, 28))
    )


def test_all_scope_runs_three_enabled_sectors_independently() -> None:
    result = run_sector_component_scope_backtest(
        config(),
        observations(),
        returns(),
        regimes(),
        portfolios(),
        SectorComponentScope(mode="all"),
    )

    assert result.status == "OK"
    assert [row.sector_id for row in result.comparison_rows] == ["SEMICONDUCTOR", "POWER_GRID", "BATTERY"]
    assert [child.sector_id for child in result.sector_results] == ["SEMICONDUCTOR", "POWER_GRID", "BATTERY"]


def test_single_scope_runs_only_selected_sector() -> None:
    result = run_sector_component_scope_backtest(
        config(),
        observations(),
        returns(),
        regimes(),
        portfolios(),
        SectorComponentScope(mode="single", sector_id="POWER_GRID"),
    )

    assert [row.sector_id for row in result.comparison_rows] == ["POWER_GRID"]
    assert [child.sector_id for child in result.sector_results] == ["POWER_GRID"]


def test_unknown_sector_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="unknown"):
        run_sector_component_scope_backtest(
            config(),
            observations(),
            returns(),
            regimes(),
            portfolios(),
            SectorComponentScope(mode="single", sector_id="UNKNOWN"),
        )


def test_missing_returns_keep_child_warning() -> None:
    result = run_sector_component_scope_backtest(
        config(),
        observations(),
        returns(include_battery=False),
        regimes(),
        portfolios(),
        SectorComponentScope(mode="single", sector_id="BATTERY"),
    )

    assert result.status == "REVIEW_REQUIRED"
    assert "HISTORICAL_RETURN_MISSING" in result.reason_codes
    assert result.comparison_rows[0].warning_count > 0


def test_comparison_row_field_completeness() -> None:
    result = run_sector_component_scope_backtest(
        config(),
        observations(),
        returns(),
        regimes(),
        portfolios(),
        SectorComponentScope(mode="single", sector_id="SEMICONDUCTOR"),
    )
    row = result.comparison_rows[0]

    assert row.display_name == "Semiconductor"
    assert row.portfolio_id == "sector_semiconductor_current_v1"
    assert row.total_return is not None
    assert row.max_drawdown is not None
    assert row.volatility is not None
    assert row.hit_rate is not None
    assert row.observation_count == 2


def test_child_result_is_never_multi_sector() -> None:
    result = run_sector_component_scope_backtest(
        config(),
        observations(),
        returns(),
        regimes(),
        portfolios(),
        SectorComponentScope(mode="all"),
    )

    assert all(child.sector_id != "MULTI_SECTOR" for child in result.sector_results)


def test_forbidden_output_keys_are_absent() -> None:
    result = run_sector_component_scope_backtest(
        config(),
        observations(),
        returns(),
        regimes(),
        portfolios(),
        SectorComponentScope(mode="all"),
    )
    payload = result.to_dict()
    forbidden = {"account_id", "order", "orders", "order_candidate", "execution", "broker"}

    assert forbidden.isdisjoint(payload)
    assert all(forbidden.isdisjoint(row) for row in payload["comparison_rows"])
    assert all(forbidden.isdisjoint(child) for child in payload["sector_results"])
