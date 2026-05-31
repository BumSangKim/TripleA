from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from api.features.backtests.sector_component_attribution import (
    SectorComponentAttributionError,
    calculate_sector_component_attribution,
)
from api.features.backtests.sector_component_models import SectorComponentObservation, SectorComponentSnapshot


AS_OF = date(2026, 5, 31)
AVAILABLE_AT = datetime(2026, 5, 30, 9, tzinfo=UTC)


def observation(component: str, score: float | None, as_of: date = AS_OF) -> SectorComponentObservation:
    return SectorComponentObservation(
        sector_id="SEMICONDUCTOR",
        component_name=component,
        score=score,
        as_of_date=as_of,
        available_at=AVAILABLE_AT,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id=f"raw-{component}",
    )


def snapshot(rows, as_of: date = AS_OF) -> SectorComponentSnapshot:
    return SectorComponentSnapshot(
        sector_id="SEMICONDUCTOR",
        as_of_date=as_of,
        available_at=AVAILABLE_AT,
        parameter_version="p1",
        model_version="m1",
        data_snapshot_id=f"snapshot-{as_of.isoformat()}",
        observations=tuple(rows),
        required_components=("trade", "demand"),
    )


def test_weighted_contribution_and_share_are_calculated() -> None:
    rows = calculate_sector_component_attribution(
        snapshot([observation("trade", 0.8), observation("demand", 0.4)]),
        {"trade": 0.75, "demand": 0.25},
    )

    by_component = {row.component_name: row for row in rows}
    assert by_component["trade"].weighted_contribution == pytest.approx(0.6)
    assert by_component["demand"].weighted_contribution == pytest.approx(0.1)
    assert sum(row.contribution_share for row in rows if row.contribution_share is not None) == pytest.approx(1.0)


def test_period_over_period_score_change_is_calculated() -> None:
    current = snapshot([observation("trade", 0.8), observation("demand", 0.4)])
    previous = snapshot([observation("trade", 0.6), observation("demand", 0.5)], as_of=date(2026, 4, 30))

    rows = calculate_sector_component_attribution(current, {"trade": 0.5, "demand": 0.5}, previous_snapshot=previous)

    assert {row.component_name: row.score_change for row in rows} == pytest.approx({"demand": -0.1, "trade": 0.2})


def test_missing_component_is_review_required_not_risk_increasing() -> None:
    rows = calculate_sector_component_attribution(snapshot([observation("trade", 0.8)]), {"trade": 0.5, "demand": 0.5})
    missing = next(row for row in rows if row.component_name == "demand")

    assert missing.weighted_contribution is None
    assert missing.contribution_share is None
    assert missing.warnings[0].fallback_state == "REVIEW_REQUIRED"
    assert "REVIEW_REQUIRED" in missing.reason_codes


def test_invalid_weight_config_is_blocked() -> None:
    with pytest.raises(SectorComponentAttributionError, match="sum to 1.0"):
        calculate_sector_component_attribution(snapshot([observation("trade", 0.8)]), {"trade": 0.7})


def test_input_order_is_deterministic() -> None:
    first = calculate_sector_component_attribution(
        snapshot([observation("demand", 0.4), observation("trade", 0.8)]),
        {"trade": 0.5, "demand": 0.5},
    )
    second = calculate_sector_component_attribution(
        snapshot([observation("trade", 0.8), observation("demand", 0.4)]),
        {"demand": 0.5, "trade": 0.5},
    )

    assert [row.to_dict() for row in first] == [row.to_dict() for row in second]


def test_invalid_score_is_warning() -> None:
    rows = calculate_sector_component_attribution(snapshot([observation("trade", 1.2)]), {"trade": 1.0})

    assert rows[0].weighted_contribution is None
    assert any(warning.code == "COMPONENT_ATTRIBUTION_SCORE_INVALID" for warning in rows[0].warnings)


def test_no_future_outcome_input_is_required_for_decision_attribution() -> None:
    rows = calculate_sector_component_attribution(snapshot([observation("trade", 0.8)]), {"trade": 1.0})
    payload = rows[0].to_dict()

    assert "future_return" not in payload
    assert "order_candidate" not in payload
    assert rows[0].reason_codes == ("SECTOR_COMPONENT_ATTRIBUTION_DIAGNOSTIC",)

