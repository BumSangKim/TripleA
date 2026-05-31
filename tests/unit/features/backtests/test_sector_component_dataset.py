from __future__ import annotations

from datetime import UTC, date, datetime

from api.features.backtests.sector_component_dataset import build_sector_component_snapshots
from api.features.backtests.sector_component_models import SectorComponentObservation


def obs(
    component: str,
    score: float | None,
    *,
    sector: str = "SEMICONDUCTOR",
    as_of: date = date(2026, 5, 1),
    available_at: datetime = datetime(2026, 5, 2, 9, tzinfo=UTC),
    snapshot_id: str = "raw-1",
    quality: float = 0.9,
) -> SectorComponentObservation:
    return SectorComponentObservation(
        sector_id=sector,
        component_name=component,
        score=score,
        as_of_date=as_of,
        available_at=available_at,
        parameter_version="raw_params_v1",
        model_version="raw_model_v1",
        data_snapshot_id=snapshot_id,
        reason_codes=("RAW_COMPONENT_OBSERVED",),
        data_quality=quality,
        source="fixture",
    )


def build(rows, decision_dates=(date(2026, 5, 31),)):
    return build_sector_component_snapshots(
        rows,
        decision_dates,
        required_components=("trade", "demand"),
        parameter_version="sector_component_v1",
        model_version="sector_component_model_v1",
        stale_after_days=20,
    )


def test_snapshot_includes_only_available_rows_for_decision_date() -> None:
    snapshots = build(
        [
            obs("trade", 0.7),
            obs("demand", 0.8, available_at=datetime(2026, 6, 1, 9, tzinfo=UTC), snapshot_id="future"),
        ]
    )

    assert len(snapshots) == 1
    assert [row.component_name for row in snapshots[0].observations] == ["trade"]
    assert all(row.data_snapshot_id != "future" for row in snapshots[0].observations)
    assert snapshots[0].requires_review


def test_future_data_leakage_is_prevented() -> None:
    snapshot = build([obs("trade", 0.7, available_at=datetime(2026, 6, 2, tzinfo=UTC))])[0]

    assert snapshot.observations == ()
    assert {warning.code for warning in snapshot.warnings} == {
        "COMPONENT_REQUIRED_INPUT_MISSING",
    }


def test_duplicate_component_uses_deterministic_latest_available_row() -> None:
    snapshots = build(
        [
            obs("trade", 0.2, as_of=date(2026, 4, 1), available_at=datetime(2026, 4, 2, tzinfo=UTC), snapshot_id="old"),
            obs("trade", 0.6, as_of=date(2026, 5, 1), available_at=datetime(2026, 5, 2, tzinfo=UTC), snapshot_id="new"),
            obs("demand", 0.5),
        ]
    )
    repeat = build(
        [
            obs("demand", 0.5),
            obs("trade", 0.6, as_of=date(2026, 5, 1), available_at=datetime(2026, 5, 2, tzinfo=UTC), snapshot_id="new"),
            obs("trade", 0.2, as_of=date(2026, 4, 1), available_at=datetime(2026, 4, 2, tzinfo=UTC), snapshot_id="old"),
        ]
    )

    assert snapshots[0].to_dict() == repeat[0].to_dict()
    assert {row.component_name: row.score for row in snapshots[0].observations}["trade"] == 0.6


def test_missing_component_remains_review_required() -> None:
    snapshot = build([obs("trade", 0.7)])[0]

    assert snapshot.fallback_state == "HOLD"
    assert any(warning.code == "COMPONENT_REQUIRED_INPUT_MISSING" for warning in snapshot.warnings)


def test_invalid_score_range_is_preserved_as_warning() -> None:
    snapshot = build([obs("trade", 1.2), obs("demand", 0.5)])[0]

    assert any(warning.code == "COMPONENT_SCORE_OUT_OF_RANGE" for warning in snapshot.warnings)
    assert snapshot.fallback_state == "HOLD"


def test_stale_data_is_warning_only() -> None:
    snapshot = build(
        [
            obs("trade", 0.7, as_of=date(2026, 4, 1), available_at=datetime(2026, 4, 2, tzinfo=UTC)),
            obs("demand", 0.5),
        ]
    )[0]

    assert any(warning.code == "COMPONENT_STALE" for warning in snapshot.warnings)
    assert snapshot.fallback_state == "HOLD"


def test_metadata_versions_and_snapshot_id_are_preserved() -> None:
    snapshot = build([obs("trade", 0.7), obs("demand", 0.8)])[0]

    assert snapshot.parameter_version == "sector_component_v1"
    assert snapshot.model_version == "sector_component_model_v1"
    assert snapshot.data_snapshot_id == "sector-component:SEMICONDUCTOR:2026-05-31:sector_component_v1"
    assert {row.source for row in snapshot.observations} == {"fixture"}

