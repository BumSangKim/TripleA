from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Mapping, Sequence

from api.features.backtests.sector_component_config import SectorComponentStressPeriod
from api.features.backtests.sector_component_models import SectorComponentValidationWarning


@dataclass(frozen=True)
class SectorComponentPeriodRecord:
    sector_id: str
    as_of_date: date
    available_at: datetime
    period_return: float
    component_contributions: dict[str, float]
    confidence: float = 1.0
    data_quality: float = 1.0
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[SectorComponentValidationWarning, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SectorComponentBreakdownResult:
    sector_id: str
    regime_metrics: dict[str, dict[str, float | int]]
    component_regime_contributions: dict[str, dict[str, float]]
    stress_period_metrics: dict[str, dict[str, float | int]]
    warning_summary: dict[str, int]
    reason_codes: tuple[str, ...]
    warnings: tuple[SectorComponentValidationWarning, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = [warning.to_dict() for warning in self.warnings]
        return payload


def calculate_regime_stress_breakdown(
    records: Sequence[SectorComponentPeriodRecord],
    *,
    regime_labels: Mapping[date, str] | None = None,
    stress_periods: Sequence[SectorComponentStressPeriod] = (),
) -> tuple[SectorComponentBreakdownResult, ...]:
    regime_labels = regime_labels or {}
    results: list[SectorComponentBreakdownResult] = []
    for sector_id in sorted({record.sector_id for record in records}):
        sector_records = sorted((record for record in records if record.sector_id == sector_id), key=lambda item: item.as_of_date)
        warnings = list(_record_warnings(sector_records))
        regime_groups: dict[str, list[SectorComponentPeriodRecord]] = {}
        for record in sector_records:
            regime = regime_labels.get(record.as_of_date)
            if not regime:
                regime = "UNKNOWN"
                warnings.append(_missing_regime_warning(record))
            regime_groups.setdefault(regime, []).append(record)
        results.append(
            SectorComponentBreakdownResult(
                sector_id=sector_id,
                regime_metrics={name: _metric_summary(items) for name, items in sorted(regime_groups.items())},
                component_regime_contributions=_component_contribution_summary(regime_groups),
                stress_period_metrics={period.name: _metric_summary(_records_in_period(sector_records, period)) for period in stress_periods},
                warning_summary=_warning_summary(warnings),
                reason_codes=("SECTOR_COMPONENT_REGIME_STRESS_DIAGNOSTIC",),
                warnings=tuple(warnings),
            )
        )
    return tuple(results)


def _metric_summary(records: Sequence[SectorComponentPeriodRecord]) -> dict[str, float | int]:
    if not records:
        return {"count": 0, "total_return": 0.0, "average_return": 0.0, "average_confidence": 0.0, "average_data_quality": 0.0}
    return {
        "count": len(records),
        "total_return": round(sum(record.period_return for record in records), 8),
        "average_return": round(sum(record.period_return for record in records) / len(records), 8),
        "average_confidence": round(sum(record.confidence for record in records) / len(records), 8),
        "average_data_quality": round(sum(record.data_quality for record in records) / len(records), 8),
    }


def _component_contribution_summary(regime_groups: Mapping[str, Sequence[SectorComponentPeriodRecord]]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for regime, records in sorted(regime_groups.items()):
        component_totals: dict[str, float] = {}
        for record in records:
            for component, contribution in record.component_contributions.items():
                component_totals[component] = component_totals.get(component, 0.0) + float(contribution)
        output[regime] = {component: round(value, 8) for component, value in sorted(component_totals.items())}
    return output


def _records_in_period(records: Sequence[SectorComponentPeriodRecord], period: SectorComponentStressPeriod) -> tuple[SectorComponentPeriodRecord, ...]:
    return tuple(record for record in records if period.start_date <= record.as_of_date <= period.end_date)


def _record_warnings(records: Sequence[SectorComponentPeriodRecord]) -> list[SectorComponentValidationWarning]:
    warnings: list[SectorComponentValidationWarning] = []
    for record in records:
        warnings.extend(record.warnings)
    return warnings


def _missing_regime_warning(record: SectorComponentPeriodRecord) -> SectorComponentValidationWarning:
    return SectorComponentValidationWarning(
        sector_id=record.sector_id,
        as_of_date=record.as_of_date,
        available_at=record.available_at,
        parameter_version="regime_breakdown",
        model_version="sector_component_breakdown_v0",
        data_snapshot_id=f"regime-breakdown:{record.sector_id}:{record.as_of_date.isoformat()}",
        reason_codes=("REVIEW_REQUIRED",),
        warnings=("MACRO_REGIME_MISSING",),
        code="MACRO_REGIME_MISSING",
        message="macro regime label is missing; UNKNOWN bucket used for diagnostics only",
    )


def _warning_summary(warnings: Sequence[SectorComponentValidationWarning]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for warning in warnings:
        summary[warning.code] = summary.get(warning.code, 0) + 1
    return dict(sorted(summary.items()))

