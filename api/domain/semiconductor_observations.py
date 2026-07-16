from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal


VALID_FREQUENCIES = frozenset({"daily", "weekly", "monthly", "quarterly", "annual", "event"})


class SemiconductorObservationError(ValueError):
    pass


@dataclass(frozen=True)
class SemiconductorDataQuality:
    quality_score: float
    missing: bool
    stale: bool
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= float(self.quality_score) <= 1.0:
            raise SemiconductorObservationError("quality_score must be between 0 and 1")
        if not isinstance(self.reason_codes, tuple) or any(not isinstance(code, str) or not code for code in self.reason_codes):
            raise SemiconductorObservationError("reason_codes must be a tuple of non-empty strings")


@dataclass(frozen=True)
class SemiconductorObservation:
    canonical_series_id: str
    value: Decimal | None
    observation_date: date
    released_at: datetime
    available_at: datetime
    updated_at: datetime
    source: str
    revision_id: str
    vintage: str
    frequency: str
    unit: str
    quality: SemiconductorDataQuality
    attributes: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("canonical_series_id", "source", "revision_id", "vintage", "frequency", "unit"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise SemiconductorObservationError(f"{field_name} must be a non-empty string")
        if self.frequency not in VALID_FREQUENCIES:
            raise SemiconductorObservationError("frequency is not supported")
        if self.observation_date is None:
            raise SemiconductorObservationError("observation_date is required")
        if self.released_at is None or self.available_at is None or self.updated_at is None:
            raise SemiconductorObservationError("released_at, available_at, and updated_at are required")
        if self.available_at < self.released_at:
            raise SemiconductorObservationError("available_at cannot be before released_at")
        if self.quality.missing and self.value is not None:
            raise SemiconductorObservationError("missing observation must not carry a value")
        if not self.quality.missing and self.value is None:
            raise SemiconductorObservationError("non-missing observation requires a value")
        if self.value is not None:
            object.__setattr__(self, "value", Decimal(str(self.value)))
        if not isinstance(self.attributes, dict):
            raise SemiconductorObservationError("attributes must be a dictionary")

    def is_available_at(self, decision_time: datetime) -> bool:
        return self.available_at <= decision_time
