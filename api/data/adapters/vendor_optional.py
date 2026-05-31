from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol, Sequence, runtime_checkable

from api.data.capex_models import RawCompanyMetricPoint, RawTimeSeriesPoint


class OptionalVendorNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class OptionalVendorMetadata:
    vendor_id: str
    license_class: str
    enabled: bool = False
    freshness_days: int | None = None
    supported_metric_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.vendor_id.strip():
            raise ValueError("vendor_id is required")
        if not self.license_class.strip():
            raise ValueError("license_class is required")
        if self.freshness_days is not None and self.freshness_days < 0:
            raise ValueError("freshness_days must be non-negative")
        object.__setattr__(self, "supported_metric_ids", tuple(self.supported_metric_ids))


@runtime_checkable
class OptionalVendorAdapter(Protocol):
    metadata: OptionalVendorMetadata

    def fetch_time_series(
        self,
        *,
        metric_id: str,
        start: date,
        end: date,
        as_of: datetime | None = None,
    ) -> Sequence[RawTimeSeriesPoint]:
        ...

    def fetch_company_metrics(
        self,
        *,
        company_ids: Sequence[str],
        metric_ids: Sequence[str],
        start_period: str | None = None,
        end_period: str | None = None,
        as_of: datetime | None = None,
    ) -> Sequence[RawCompanyMetricPoint]:
        ...


@dataclass
class DisabledOptionalVendorAdapter:
    metadata: OptionalVendorMetadata = field(
        default_factory=lambda: OptionalVendorMetadata(
            vendor_id="optional_licensed_vendor",
            license_class="licensed_vendor_required",
            enabled=False,
            freshness_days=None,
            supported_metric_ids=(),
        )
    )

    def fetch_time_series(
        self,
        *,
        metric_id: str,
        start: date,
        end: date,
        as_of: datetime | None = None,
    ) -> tuple[RawTimeSeriesPoint, ...]:
        raise OptionalVendorNotConfiguredError(_message(self.metadata.vendor_id))

    def fetch_company_metrics(
        self,
        *,
        company_ids: Sequence[str],
        metric_ids: Sequence[str],
        start_period: str | None = None,
        end_period: str | None = None,
        as_of: datetime | None = None,
    ) -> tuple[RawCompanyMetricPoint, ...]:
        raise OptionalVendorNotConfiguredError(_message(self.metadata.vendor_id))


def _message(vendor_id: str) -> str:
    return f"Optional licensed vendor '{vendor_id}' is not configured; REVIEW_REQUIRED"
