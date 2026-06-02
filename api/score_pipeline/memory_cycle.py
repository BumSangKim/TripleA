from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Iterable

from api.score_pipeline.contracts import PipelineContractError


ALLOWED_MEMORY_CYCLE_PROXIES = frozenset(
    {
        "dram_asp_index",
        "nand_asp_index",
        "memory_inventory_index",
        "memory_revenue_growth",
        "memory_margin_proxy",
        "memory_capex_growth",
        "semiconductor_memory_index",
        "hbm_asp_proxy",
    }
)


class MemoryCycleCoverageStatus(str, Enum):
    PASS_TWO_OR_MORE_CYCLES = "PASS_TWO_OR_MORE_CYCLES"
    INSUFFICIENT_MEMORY_CYCLE_COVERAGE = "INSUFFICIENT_MEMORY_CYCLE_COVERAGE"
    INSUFFICIENT_PROXY_DATA = "INSUFFICIENT_PROXY_DATA"
    AMBIGUOUS_CYCLE_BOUNDARIES = "AMBIGUOUS_CYCLE_BOUNDARIES"
    LEAKAGE_UNSAFE_DATA = "LEAKAGE_UNSAFE_DATA"


@dataclass(frozen=True)
class MemoryCycleProxyPoint:
    proxy_name: str
    observed_on: date
    value: float
    available_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.proxy_name, "proxy_name")
        if self.proxy_name not in ALLOWED_MEMORY_CYCLE_PROXIES:
            raise PipelineContractError("proxy_name is not allowed for memory cycle coverage")
        if self.observed_on is None:
            raise PipelineContractError("observed_on is required")
        if self.available_at is None:
            raise PipelineContractError("available_at is required")
        float(self.value)


@dataclass(frozen=True)
class MemoryCycleSegment:
    proxy_name: str
    pattern: str
    start_date: date
    middle_date: date
    end_date: date
    start_value: float
    middle_value: float
    end_value: float

    def __post_init__(self) -> None:
        _require_text(self.proxy_name, "proxy_name")
        if self.pattern not in {"peak_trough_recovery", "trough_peak_normalization"}:
            raise PipelineContractError("unsupported memory cycle segment pattern")
        if not (self.start_date < self.middle_date < self.end_date):
            raise PipelineContractError("cycle segment dates must be strictly ordered")


@dataclass(frozen=True)
class MemoryCycleCoverageReport:
    status: MemoryCycleCoverageStatus
    complete_cycle_count: int
    proxy_names_used: tuple[str, ...]
    cycle_boundaries: tuple[MemoryCycleSegment, ...]
    backtest_start: date
    backtest_end: date
    decision_date: date
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, MemoryCycleCoverageStatus):
            raise PipelineContractError("status must be a MemoryCycleCoverageStatus")
        if self.complete_cycle_count < 0:
            raise PipelineContractError("complete_cycle_count cannot be negative")
        if self.backtest_start is None or self.backtest_end is None or self.decision_date is None:
            raise PipelineContractError("backtest and decision dates are required")
        if self.backtest_start > self.backtest_end:
            raise PipelineContractError("backtest_start cannot be after backtest_end")
        if self.backtest_end > self.decision_date:
            raise PipelineContractError("backtest_end cannot be after decision_date")
        if self.status == MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES and self.complete_cycle_count < 2:
            raise PipelineContractError("PASS_TWO_OR_MORE_CYCLES requires at least two complete cycles")
        _require_text_tuple(self.proxy_names_used, "proxy_names_used")
        _require_text_tuple(self.reason_codes, "reason_codes")
        _require_text_tuple(self.warnings, "warnings")

    @property
    def tuning_allowed(self) -> bool:
        return self.status == MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES


@dataclass(frozen=True)
class _Boundary:
    kind: str
    point: MemoryCycleProxyPoint


def evaluate_memory_cycle_coverage(
    points: Iterable[MemoryCycleProxyPoint],
    *,
    backtest_start: date,
    backtest_end: date,
    decision_date: date,
    min_points: int = 6,
    min_swing_ratio: float = 0.12,
) -> MemoryCycleCoverageReport:
    if backtest_start > backtest_end:
        raise PipelineContractError("backtest_start cannot be after backtest_end")
    if backtest_end > decision_date:
        raise PipelineContractError("backtest_end cannot be after decision_date")
    if min_points <= 0:
        raise PipelineContractError("min_points must be positive")
    if not 0.0 < min_swing_ratio < 1.0:
        raise PipelineContractError("min_swing_ratio must be between 0 and 1")

    safe_points, future_excluded = _filter_safe_points(points, backtest_start, backtest_end, decision_date)
    if not safe_points:
        status = MemoryCycleCoverageStatus.LEAKAGE_UNSAFE_DATA if future_excluded else MemoryCycleCoverageStatus.INSUFFICIENT_PROXY_DATA
        return _report(status, (), (), backtest_start, backtest_end, decision_date, future_excluded=future_excluded)

    cycles: list[MemoryCycleSegment] = []
    proxy_names_used: set[str] = set()
    grouped: dict[str, list[MemoryCycleProxyPoint]] = {}
    for point in safe_points:
        grouped.setdefault(point.proxy_name, []).append(point)

    insufficient_groups = 0
    ambiguous_groups = 0
    for proxy_name, proxy_points in grouped.items():
        ordered = sorted(proxy_points, key=lambda item: item.observed_on)
        if len(ordered) < min_points:
            insufficient_groups += 1
            continue
        boundaries = _detect_boundaries(ordered, min_swing_ratio=min_swing_ratio)
        proxy_cycles = _segments_from_boundaries(boundaries)
        if not proxy_cycles:
            ambiguous_groups += 1
            continue
        proxy_names_used.add(proxy_name)
        cycles.extend(proxy_cycles)

    cycles = sorted(cycles, key=lambda segment: (segment.start_date, segment.end_date))
    if len(cycles) >= 2:
        return _report(
            MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES,
            tuple(sorted(proxy_names_used)),
            tuple(cycles),
            backtest_start,
            backtest_end,
            decision_date,
            future_excluded=future_excluded,
        )
    if cycles:
        status = MemoryCycleCoverageStatus.INSUFFICIENT_MEMORY_CYCLE_COVERAGE
    elif insufficient_groups and not ambiguous_groups:
        status = MemoryCycleCoverageStatus.INSUFFICIENT_PROXY_DATA
    else:
        status = MemoryCycleCoverageStatus.AMBIGUOUS_CYCLE_BOUNDARIES
    return _report(
        status,
        tuple(sorted(proxy_names_used)),
        tuple(cycles),
        backtest_start,
        backtest_end,
        decision_date,
        future_excluded=future_excluded,
    )


def _filter_safe_points(
    points: Iterable[MemoryCycleProxyPoint],
    backtest_start: date,
    backtest_end: date,
    decision_date: date,
) -> tuple[list[MemoryCycleProxyPoint], bool]:
    safe_points: list[MemoryCycleProxyPoint] = []
    future_excluded = False
    for point in points:
        if point.available_at.date() > decision_date:
            future_excluded = True
            continue
        if not backtest_start <= point.observed_on <= backtest_end:
            continue
        safe_points.append(point)
    return safe_points, future_excluded


def _detect_boundaries(
    points: list[MemoryCycleProxyPoint],
    *,
    min_swing_ratio: float,
) -> list[_Boundary]:
    candidates: list[_Boundary] = []
    for index, point in enumerate(points):
        previous_value = points[index - 1].value if index > 0 else None
        next_value = points[index + 1].value if index < len(points) - 1 else None
        if previous_value is None and next_value is not None:
            kind = "peak" if point.value > next_value else "trough" if point.value < next_value else None
        elif next_value is None and previous_value is not None:
            kind = "peak" if point.value > previous_value else "trough" if point.value < previous_value else None
        elif previous_value is not None and next_value is not None:
            kind = "peak" if point.value >= previous_value and point.value >= next_value else "trough" if point.value <= previous_value and point.value <= next_value else None
        else:
            kind = None
        if kind:
            candidates.append(_Boundary(kind, point))

    alternating: list[_Boundary] = []
    for boundary in candidates:
        if not alternating:
            alternating.append(boundary)
            continue
        last = alternating[-1]
        if boundary.kind == last.kind:
            if _is_more_extreme(boundary, last):
                alternating[-1] = boundary
            continue
        if _swing_ratio(last.point.value, boundary.point.value) >= min_swing_ratio:
            alternating.append(boundary)
    return alternating


def _segments_from_boundaries(boundaries: list[_Boundary]) -> list[MemoryCycleSegment]:
    segments: list[MemoryCycleSegment] = []
    index = 0
    while index + 2 < len(boundaries):
        first, second, third = boundaries[index], boundaries[index + 1], boundaries[index + 2]
        if first.kind == "peak" and second.kind == "trough" and third.kind == "peak":
            segments.append(_segment("peak_trough_recovery", first, second, third))
            index += 2
            continue
        if first.kind == "trough" and second.kind == "peak" and third.kind == "trough":
            segments.append(_segment("trough_peak_normalization", first, second, third))
            index += 2
            continue
        index += 1
    return segments


def _segment(pattern: str, first: _Boundary, second: _Boundary, third: _Boundary) -> MemoryCycleSegment:
    return MemoryCycleSegment(
        proxy_name=first.point.proxy_name,
        pattern=pattern,
        start_date=first.point.observed_on,
        middle_date=second.point.observed_on,
        end_date=third.point.observed_on,
        start_value=first.point.value,
        middle_value=second.point.value,
        end_value=third.point.value,
    )


def _report(
    status: MemoryCycleCoverageStatus,
    proxy_names_used: tuple[str, ...],
    cycles: tuple[MemoryCycleSegment, ...],
    backtest_start: date,
    backtest_end: date,
    decision_date: date,
    *,
    future_excluded: bool,
) -> MemoryCycleCoverageReport:
    reason_codes: list[str] = []
    warnings: list[str] = []
    if status != MemoryCycleCoverageStatus.PASS_TWO_OR_MORE_CYCLES:
        reason_codes.append(status.value)
    if future_excluded:
        reason_codes.append("FUTURE_PROXY_POINTS_EXCLUDED")
        warnings.append("future available_at proxy points were excluded from memory cycle proof")
    return MemoryCycleCoverageReport(
        status=status,
        complete_cycle_count=len(cycles),
        proxy_names_used=proxy_names_used,
        cycle_boundaries=cycles,
        backtest_start=backtest_start,
        backtest_end=backtest_end,
        decision_date=decision_date,
        reason_codes=tuple(reason_codes),
        warnings=tuple(warnings),
    )


def _is_more_extreme(candidate: _Boundary, current: _Boundary) -> bool:
    if candidate.kind == "peak":
        return candidate.point.value > current.point.value
    return candidate.point.value < current.point.value


def _swing_ratio(first: float, second: float) -> float:
    denominator = max(abs(first), abs(second), 1e-9)
    return abs(second - first) / denominator


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PipelineContractError(f"{field_name} must be a non-empty string")


def _require_text_tuple(value: tuple[str, ...], field_name: str) -> None:
    if not isinstance(value, tuple):
        raise PipelineContractError(f"{field_name} must be a tuple")
    for item in value:
        _require_text(item, field_name)
