from __future__ import annotations

from datetime import UTC, date, datetime

from api.features.backtests.sector_component_breakdown import (
    SectorComponentPeriodRecord,
    calculate_regime_stress_breakdown,
)
from api.features.backtests.sector_component_config import SectorComponentStressPeriod
from api.features.backtests.sector_component_models import SectorComponentValidationWarning


AVAILABLE_AT = datetime(2026, 5, 31, 9, tzinfo=UTC)


def record(as_of: date, period_return: float, *, sector: str = "SEMICONDUCTOR") -> SectorComponentPeriodRecord:
    return SectorComponentPeriodRecord(
        sector_id=sector,
        as_of_date=as_of,
        available_at=AVAILABLE_AT,
        period_return=period_return,
        component_contributions={"trade": 0.2, "demand": 0.3},
        confidence=0.8,
        data_quality=0.9,
    )


def test_regime_metric_breakdown() -> None:
    result = calculate_regime_stress_breakdown(
        [record(date(2026, 1, 31), 0.02), record(date(2026, 2, 28), -0.01)],
        regime_labels={date(2026, 1, 31): "risk_on", date(2026, 2, 28): "risk_off"},
    )[0]

    assert result.regime_metrics["risk_on"]["total_return"] == 0.02
    assert result.regime_metrics["risk_off"]["total_return"] == -0.01


def test_stress_period_breakdown_uses_config_only() -> None:
    result = calculate_regime_stress_breakdown(
        [record(date(2026, 1, 31), 0.02), record(date(2026, 3, 31), -0.03)],
        regime_labels={date(2026, 1, 31): "risk_on", date(2026, 3, 31): "risk_off"},
        stress_periods=(SectorComponentStressPeriod("q1_stress", date(2026, 3, 1), date(2026, 3, 31)),),
    )[0]

    assert set(result.stress_period_metrics) == {"q1_stress"}
    assert result.stress_period_metrics["q1_stress"]["total_return"] == -0.03


def test_missing_macro_regime_is_conservative_warning() -> None:
    result = calculate_regime_stress_breakdown([record(date(2026, 1, 31), 0.02)])[0]

    assert "UNKNOWN" in result.regime_metrics
    assert result.warning_summary["MACRO_REGIME_MISSING"] == 1
    assert result.warnings[0].fallback_state == "REVIEW_REQUIRED"


def test_dominant_regime_is_not_fixed_weight_mapping() -> None:
    result = calculate_regime_stress_breakdown(
        [record(date(2026, 1, 31), 0.02)],
        regime_labels={date(2026, 1, 31): "risk_on"},
    )[0]
    payload = result.to_dict()

    assert "target_weight" not in payload
    assert "allocation_switch" not in payload
    assert result.reason_codes == ("SECTOR_COMPONENT_REGIME_STRESS_DIAGNOSTIC",)


def test_component_contribution_is_preserved_by_regime() -> None:
    result = calculate_regime_stress_breakdown(
        [record(date(2026, 1, 31), 0.02)],
        regime_labels={date(2026, 1, 31): "risk_on"},
    )[0]

    assert result.component_regime_contributions["risk_on"] == {"demand": 0.3, "trade": 0.2}


def test_warning_summary_includes_record_quality_warnings() -> None:
    warning = SectorComponentValidationWarning(
        sector_id="SEMICONDUCTOR",
        as_of_date=date(2026, 1, 31),
        available_at=AVAILABLE_AT,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id="snapshot-1",
        code="LOW_DATA_QUALITY",
        message="low quality",
    )
    low_quality = SectorComponentPeriodRecord(
        sector_id="SEMICONDUCTOR",
        as_of_date=date(2026, 1, 31),
        available_at=AVAILABLE_AT,
        period_return=0.0,
        component_contributions={"trade": 0.1},
        warnings=(warning,),
    )

    result = calculate_regime_stress_breakdown([low_quality], regime_labels={date(2026, 1, 31): "risk_on"})[0]

    assert result.warning_summary["LOW_DATA_QUALITY"] == 1

