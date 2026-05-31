from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, Sequence, runtime_checkable


NumericValue = int | float | Decimal


class DataAdapterContractError(ValueError):
    pass


@dataclass(frozen=True)
class TimeSeriesPoint:
    series_id: str
    value: NumericValue | None
    observation_date: date
    available_at: datetime
    updated_at: datetime
    source: str
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.series_id, "series_id")
        _require_text(self.source, "source")
        if self.observation_date is None:
            raise DataAdapterContractError("observation_date is required")
        if self.available_at is None:
            raise DataAdapterContractError("available_at is required")
        if self.updated_at is None:
            raise DataAdapterContractError("updated_at is required")


@runtime_checkable
class CapexInputAdapter(Protocol):
    adapter_name: str

    def list_series(self) -> Sequence[str]:
        ...

    def fetch_series(
        self,
        series_id: str,
        *,
        start: date | None = None,
        end: date | None = None,
        as_of: datetime | None = None,
    ) -> Sequence[TimeSeriesPoint]:
        ...


@runtime_checkable
class CompanyMetricAdapter(Protocol):
    adapter_name: str

    def list_metrics(self, company_id: str | None = None) -> Sequence[str]:
        ...

    def fetch_metric(
        self,
        company_id: str,
        metric_id: str,
        *,
        start: date | None = None,
        end: date | None = None,
        as_of: datetime | None = None,
    ) -> Sequence[TimeSeriesPoint]:
        ...


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DataAdapterContractError(f"{field_name} must be a non-empty string")
