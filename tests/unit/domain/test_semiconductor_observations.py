from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from api.domain.semiconductor_observations import (
    SemiconductorDataQuality,
    SemiconductorObservation,
    SemiconductorObservationError,
)


def _quality(*, missing: bool = False) -> SemiconductorDataQuality:
    return SemiconductorDataQuality(quality_score=0.0 if missing else 0.9, missing=missing, stale=False)


def test_observation_is_immutable_and_keeps_point_in_time_metadata():
    released_at = datetime(2026, 2, 5, 9, tzinfo=UTC)
    observation = SemiconductorObservation(
        canonical_series_id="semiconductor.memory.dram_spot_price_index",
        value=Decimal("100"),
        observation_date=date(2026, 1, 31),
        released_at=released_at,
        available_at=released_at,
        updated_at=released_at,
        source="fixture",
        revision_id="initial",
        vintage="2026-02-05",
        frequency="monthly",
        unit="index",
        quality=_quality(),
    )

    assert observation.is_available_at(released_at)
    with pytest.raises(Exception):
        observation.value = Decimal("101")  # type: ignore[misc]


def test_missing_observation_requires_null_value():
    released_at = datetime(2026, 2, 5, 9, tzinfo=UTC)

    with pytest.raises(SemiconductorObservationError, match="missing observation"):
        SemiconductorObservation(
            canonical_series_id="semiconductor.inventory.channel_days",
            value=Decimal("20"),
            observation_date=date(2026, 1, 31),
            released_at=released_at,
            available_at=released_at,
            updated_at=released_at,
            source="fixture",
            revision_id="missing",
            vintage="2026-02-05",
            frequency="monthly",
            unit="days",
            quality=_quality(missing=True),
        )
