from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence

from api.domain.semiconductor_observations import SemiconductorDataQuality, SemiconductorObservation
from api.score_pipeline.contracts import DecisionWarning
from api.score_pipeline.data_quality import HistoricalSnapshot, RawDataPoint


class FixtureSemiconductorObservationRepository:
    """Immutable, fixture-only point-in-time observation repository."""

    def __init__(self, observations: Sequence[SemiconductorObservation]) -> None:
        self._observations = tuple(observations)

    @classmethod
    def from_rows(cls, rows: Sequence[Mapping[str, Any]]) -> "FixtureSemiconductorObservationRepository":
        return cls(tuple(_observation_from_row(row) for row in rows))

    def select_latest(self, canonical_series_id: str, *, decision_time: datetime) -> SemiconductorObservation | None:
        eligible = [
            observation
            for observation in self._observations
            if observation.canonical_series_id == canonical_series_id and observation.is_available_at(decision_time)
        ]
        if not eligible:
            return None
        return max(
            eligible,
            key=lambda observation: (
                observation.observation_date,
                observation.available_at,
                observation.updated_at,
                observation.revision_id,
            ),
        )

    def build_snapshot(
        self,
        *,
        snapshot_id: str,
        decision_time: datetime,
        canonical_series_ids: Sequence[str],
    ) -> HistoricalSnapshot:
        points: dict[str, RawDataPoint] = {}
        warnings: list[DecisionWarning] = []
        for series_id in canonical_series_ids:
            observation = self.select_latest(series_id, decision_time=decision_time)
            if observation is None:
                warnings.append(
                    DecisionWarning("SEMICONDUCTOR_RAW_OBSERVATION_UNAVAILABLE", "WARNING", "semiconductor_fixture", series_id)
                )
                continue
            if observation.quality.missing or observation.value is None:
                warnings.append(
                    DecisionWarning("SEMICONDUCTOR_RAW_OBSERVATION_MISSING", "WARNING", "semiconductor_fixture", series_id)
                )
                continue
            points[series_id] = RawDataPoint(
                key=series_id,
                value=float(observation.value),
                source=observation.source,
                as_of_date=observation.observation_date,
                available_at=observation.available_at,
                updated_at=observation.updated_at,
                revision_id=observation.revision_id,
            )
        return HistoricalSnapshot(snapshot_id, decision_time.date(), points, warnings)


def _observation_from_row(row: Mapping[str, Any]) -> SemiconductorObservation:
    quality = row.get("quality") or {}
    return SemiconductorObservation(
        canonical_series_id=str(row["canonical_series_id"]),
        value=None if row.get("value") is None else Decimal(str(row["value"])),
        observation_date=datetime.fromisoformat(str(row["observation_date"])).date(),
        released_at=datetime.fromisoformat(str(row["released_at"])),
        available_at=datetime.fromisoformat(str(row["available_at"])),
        updated_at=datetime.fromisoformat(str(row["updated_at"])),
        source=str(row["source"]),
        revision_id=str(row["revision_id"]),
        vintage=str(row["vintage"]),
        frequency=str(row["frequency"]),
        unit=str(row["unit"]),
        quality=SemiconductorDataQuality(
            quality_score=float(quality["quality_score"]),
            missing=bool(quality["missing"]),
            stale=bool(quality["stale"]),
            reason_codes=tuple(str(code) for code in quality.get("reason_codes", ())),
        ),
        attributes={str(key): str(value) for key, value in (row.get("attributes") or {}).items()},
    )
