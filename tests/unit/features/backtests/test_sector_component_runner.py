from __future__ import annotations

from datetime import UTC, date, datetime

from api.features.backtests.sector_component_config import (
    SectorComponentBacktestConfig,
    SectorComponentStressPeriod,
    SectorComponentWeightSet,
)
from api.features.backtests.sector_component_models import SectorComponentObservation
from api.features.backtests.sector_component_runner import (
    SectorComponentRegimeRecord,
    SectorComponentReturnRecord,
    run_sector_component_backtest,
)


def config() -> SectorComponentBacktestConfig:
    return SectorComponentBacktestConfig(
        parameter_version="p1",
        model_version="m1",
        enabled_components=("trade", "demand"),
        component_weight_grid=(
            SectorComponentWeightSet("balanced", {"trade": 0.5, "demand": 0.5}),
            SectorComponentWeightSet("trade_heavy", {"trade": 0.8, "demand": 0.2}),
        ),
        rebalance_frequency="monthly",
        decision_lag_days=1,
        transaction_cost_bps=10.0,
        tax_assumption_enabled=False,
        stress_periods=(SectorComponentStressPeriod("q1_review", date(2026, 1, 1), date(2026, 3, 31)),),
        required_metrics=("total_return", "max_drawdown", "volatility", "hit_rate"),
        fallback_policy="REVIEW_REQUIRED",
    )


def observation(
    component: str,
    score: float | None,
    as_of: date,
    *,
    available_at: datetime | None = None,
    quality: float = 1.0,
) -> SectorComponentObservation:
    available_at = available_at or datetime(2026, as_of.month, min(as_of.day, 28), 9, tzinfo=UTC)
    return SectorComponentObservation(
        sector_id="SEMICONDUCTOR",
        component_name=component,
        score=score,
        as_of_date=as_of,
        available_at=available_at,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id=f"raw:{component}:{as_of.isoformat()}:{available_at.isoformat()}",
        data_quality=quality,
    )


def observations() -> tuple[SectorComponentObservation, ...]:
    return (
        observation("trade", 0.6, date(2026, 1, 31), available_at=datetime(2026, 1, 30, 9, tzinfo=UTC)),
        observation("demand", 0.4, date(2026, 1, 31), available_at=datetime(2026, 1, 30, 9, tzinfo=UTC)),
        observation("trade", 0.7, date(2026, 2, 28), available_at=datetime(2026, 2, 27, 9, tzinfo=UTC)),
        observation("demand", 0.5, date(2026, 2, 28), available_at=datetime(2026, 2, 27, 9, tzinfo=UTC)),
        observation("trade", 0.8, date(2026, 3, 31), available_at=datetime(2026, 3, 30, 9, tzinfo=UTC)),
        observation("demand", 0.6, date(2026, 3, 31), available_at=datetime(2026, 3, 30, 9, tzinfo=UTC)),
    )


def returns() -> tuple[SectorComponentReturnRecord, ...]:
    return (
        SectorComponentReturnRecord("SEMICONDUCTOR", date(2026, 1, 31), 0.02),
        SectorComponentReturnRecord("SEMICONDUCTOR", date(2026, 2, 28), -0.01),
        SectorComponentReturnRecord("SEMICONDUCTOR", date(2026, 3, 31), 0.03),
    )


def regimes() -> tuple[SectorComponentRegimeRecord, ...]:
    return (
        SectorComponentRegimeRecord("SEMICONDUCTOR", date(2026, 1, 31), "risk_on"),
        SectorComponentRegimeRecord("SEMICONDUCTOR", date(2026, 2, 28), "risk_off"),
        SectorComponentRegimeRecord("SEMICONDUCTOR", date(2026, 3, 31), "risk_on"),
    )


def test_normal_input_builds_result() -> None:
    result = run_sector_component_backtest(config(), observations(), returns(), macro_regime_records=regimes())

    assert result.status == "OK"
    assert result.sector_id == "SEMICONDUCTOR"
    assert result.metric_summaries[0].observation_count == 3
    assert result.metric_summaries[0].total_return == 0.025
    assert len(result.attribution_rows) == 6


def test_raw_observation_to_snapshot_attribution_metric_output_flow_is_preserved() -> None:
    raw_observations = [item.to_dict() for item in observations()]
    result = run_sector_component_backtest(config(), raw_observations, returns(), macro_regime_records=regimes())

    assert result.attribution_rows[0].data_snapshot_id.startswith("sector-component:SEMICONDUCTOR")
    assert {row.component_name for row in result.attribution_rows} == {"trade", "demand"}
    assert result.metric_summaries[0].reason_codes == ("SECTOR_COMPONENT_BACKTEST_METRIC_SUMMARY",)


def test_future_data_leakage_is_blocked() -> None:
    future_only = observation(
        "trade",
        1.0,
        date(2026, 4, 30),
        available_at=datetime(2026, 4, 1, 9, tzinfo=UTC),
    )
    result = run_sector_component_backtest(config(), (*observations(), future_only), returns(), macro_regime_records=regimes())
    january_trade = [
        row
        for row in result.attribution_rows
        if row.as_of_date == date(2026, 1, 31) and row.component_name == "trade"
    ][0]

    assert january_trade.score == 0.6


def test_missing_component_and_return_are_conservative_fallbacks() -> None:
    missing_demand = tuple(item for item in observations() if item.component_name != "demand")
    missing_return = returns()[:-1]
    result = run_sector_component_backtest(config(), missing_demand, missing_return, macro_regime_records=regimes())

    assert result.status == "REVIEW_REQUIRED"
    assert "COMPONENT_REQUIRED_INPUT_MISSING" in result.reason_codes
    assert "HISTORICAL_RETURN_MISSING" in result.reason_codes


def test_low_data_quality_warning_is_returned() -> None:
    low_quality = (
        observation("trade", 0.6, date(2026, 1, 31), available_at=datetime(2026, 1, 30, 9, tzinfo=UTC), quality=0.2),
        observation("demand", 0.4, date(2026, 1, 31), available_at=datetime(2026, 1, 30, 9, tzinfo=UTC)),
    )
    result = run_sector_component_backtest(config(), low_quality, returns()[:1], macro_regime_records=regimes()[:1])

    assert result.status == "REVIEW_REQUIRED"
    assert any(warning.code == "SECTOR_COMPONENT_LOW_DATA_QUALITY" for warning in result.warnings)


def test_parameter_sensitivity_results_are_included_without_approval() -> None:
    result = run_sector_component_backtest(config(), observations(), returns(), macro_regime_records=regimes())

    assert {item.parameter_set_id for item in result.sensitivity_results} == {"balanced", "trade_heavy"}
    assert all(item.approved_for_production is False for item in result.sensitivity_results)


def test_regime_and_stress_breakdowns_are_included() -> None:
    result = run_sector_component_backtest(config(), observations(), returns(), macro_regime_records=regimes())
    breakdown = result.regime_breakdowns[0]

    assert set(breakdown["regime_metrics"]) == {"risk_off", "risk_on"}
    assert set(breakdown["stress_period_metrics"]) == {"q1_review"}


def test_result_has_no_order_candidate_or_execution_output() -> None:
    result = run_sector_component_backtest(config(), observations(), returns(), macro_regime_records=regimes())
    payload = result.to_dict()

    assert "order_candidate" not in payload
    assert "orders" not in payload
    assert "execution" not in payload
    assert "account_id" not in payload


def test_fixed_input_is_reproducible() -> None:
    first = run_sector_component_backtest(config(), observations(), returns(), macro_regime_records=regimes())
    second = run_sector_component_backtest(
        config(),
        tuple(reversed(observations())),
        tuple(reversed(returns())),
        macro_regime_records=tuple(reversed(regimes())),
    )

    assert first.to_dict() == second.to_dict()
