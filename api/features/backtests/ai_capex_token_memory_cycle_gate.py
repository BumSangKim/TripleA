from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


PASS_STATUS = "PASS_TWO_MEMORY_CYCLES"
REVIEW_STATUS = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class MemoryCycleCoverage:
    status: str
    distinct_cycle_count: int
    cycle_ids: tuple[str, ...]
    historical_tuning_allowed: bool
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.status not in {PASS_STATUS, REVIEW_STATUS}:
            raise ValueError("status must be PASS_TWO_MEMORY_CYCLES or REVIEW_REQUIRED")
        if self.distinct_cycle_count < 0:
            raise ValueError("distinct_cycle_count cannot be negative")
        _coerce_tuple(self, "cycle_ids")
        _coerce_tuple(self, "reason_codes")
        _coerce_tuple(self, "warnings")
        if self.status == PASS_STATUS and self.distinct_cycle_count < 2:
            raise ValueError("PASS_TWO_MEMORY_CYCLES requires at least two explicit cycles")
        if self.historical_tuning_allowed is not (self.status == PASS_STATUS):
            raise ValueError("historical_tuning_allowed must match status")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_two_memory_cycle_coverage(snapshots: Sequence[Any]) -> MemoryCycleCoverage:
    cycle_ids = sorted({_cycle_id(snapshot) for snapshot in snapshots if _cycle_id(snapshot)})
    if len(cycle_ids) >= 2:
        return MemoryCycleCoverage(
            status=PASS_STATUS,
            distinct_cycle_count=len(cycle_ids),
            cycle_ids=tuple(cycle_ids),
            historical_tuning_allowed=True,
            reason_codes=("TWO_MEMORY_CYCLE_COVERAGE_PASSED",),
        )
    if not snapshots:
        reason = "MEMORY_CYCLE_SNAPSHOTS_MISSING"
        warning = "no snapshots were provided"
    elif not cycle_ids:
        reason = "MEMORY_CYCLE_ID_MISSING"
        warning = "explicit memory_cycle_id metadata is missing"
    else:
        reason = "INSUFFICIENT_MEMORY_CYCLE_COVERAGE"
        warning = "fewer than two distinct explicit memory cycles were found"
    return MemoryCycleCoverage(
        status=REVIEW_STATUS,
        distinct_cycle_count=len(cycle_ids),
        cycle_ids=tuple(cycle_ids),
        historical_tuning_allowed=False,
        reason_codes=(reason,),
        warnings=(warning,),
    )


def _cycle_id(snapshot: Any) -> str | None:
    metadata = _metadata(snapshot)
    value = metadata.get("memory_cycle_id")
    if value is None:
        value = metadata.get("cycle_id")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata(snapshot: Any) -> Mapping[str, Any]:
    if isinstance(snapshot, Mapping):
        metadata = snapshot.get("metadata")
        if isinstance(metadata, Mapping):
            return metadata
        row_metadata = snapshot.get("row_metadata")
        if isinstance(row_metadata, Mapping):
            return row_metadata
        return snapshot
    metadata = getattr(snapshot, "metadata", None)
    if isinstance(metadata, Mapping):
        return metadata
    row_metadata = getattr(snapshot, "row_metadata", None)
    if isinstance(row_metadata, Mapping):
        return row_metadata
    return {}


def _coerce_tuple(instance: Any, field_name: str) -> None:
    value = getattr(instance, field_name)
    if not isinstance(value, tuple):
        object.__setattr__(instance, field_name, tuple(value))
