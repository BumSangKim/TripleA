from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from api.score_pipeline.contracts import ConservativeAction, DecisionWarning, ParameterVersionRef


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARAMETER_PATH = PROJECT_ROOT / "config" / "parameters" / "default.yaml"


class ParameterRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class ParameterEntry:
    name: str
    value: Any
    version: str
    valid_from: date
    valid_to: date | None
    source: str
    reason: str
    approved: bool
    backtest_result: str | None = None
    walk_forward_result: str | None = None
    rollback_condition: str | None = None
    affected_modules: list[str] = field(default_factory=list)

    def is_active_on(self, as_of_date: date) -> bool:
        if not self.approved:
            return False
        if as_of_date < self.valid_from:
            return False
        if self.valid_to is not None and as_of_date > self.valid_to:
            return False
        return True


@dataclass(frozen=True)
class ParameterLookup:
    name: str
    value: Any
    version_ref: ParameterVersionRef
    conservative_action: str | None
    warnings: list[DecisionWarning] = field(default_factory=list)


class ParameterRegistry:
    def __init__(self, entries: list[ParameterEntry], fallback_policy: str = ConservativeAction.REVIEW_REQUIRED):
        if fallback_policy not in ConservativeAction.values():
            raise ParameterRegistryError("fallback_policy must be conservative")
        self.entries_by_name: dict[str, list[ParameterEntry]] = {}
        self.fallback_policy = fallback_policy
        for entry in entries:
            self.entries_by_name.setdefault(entry.name, []).append(entry)

    @classmethod
    def from_yaml(cls, path: str | Path = DEFAULT_PARAMETER_PATH) -> "ParameterRegistry":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        fallback = raw.get("fallback_policy", ConservativeAction.REVIEW_REQUIRED)
        entries = [_entry(item) for item in raw.get("parameters", [])]
        return cls(entries, fallback)

    def get(self, name: str, *, as_of_date: date, expected_type: type | tuple[type, ...] | None = None) -> ParameterLookup:
        candidates = self.entries_by_name.get(name) or []
        active = [entry for entry in candidates if entry.is_active_on(as_of_date)]
        if not active:
            return self._fallback(name, "MISSING_OR_INACTIVE_PARAMETER")
        entry = sorted(active, key=lambda item: item.valid_from)[-1]
        if expected_type is not None and not isinstance(entry.value, expected_type):
            return self._fallback(name, "INVALID_PARAMETER_TYPE")
        return ParameterLookup(
            name=name,
            value=entry.value,
            version_ref=ParameterVersionRef(entry.version, entry.source),
            conservative_action=None,
            warnings=[],
        )

    def parameter_version_for(self, names: list[str], as_of_date: date) -> str:
        versions = []
        for name in names:
            lookup = self.get(name, as_of_date=as_of_date)
            versions.append(lookup.version_ref.version)
        return "+".join(sorted(set(versions)))

    def _fallback(self, name: str, code: str) -> ParameterLookup:
        return ParameterLookup(
            name=name,
            value=None,
            version_ref=ParameterVersionRef("unavailable", "parameter_registry"),
            conservative_action=self.fallback_policy,
            warnings=[DecisionWarning(code, "WARNING", "parameter_registry", f"{name} fell back to {self.fallback_policy}")],
        )


def _entry(raw: dict[str, Any]) -> ParameterEntry:
    try:
        valid_from = date.fromisoformat(str(raw["valid_from"]))
        valid_to = raw.get("valid_to")
        return ParameterEntry(
            name=str(raw["name"]),
            value=raw.get("value"),
            version=str(raw["version"]),
            valid_from=valid_from,
            valid_to=None if valid_to in {None, ""} else date.fromisoformat(str(valid_to)),
            source=str(raw["source"]),
            reason=str(raw["reason"]),
            approved=bool(raw["approved"]),
            backtest_result=raw.get("backtest_result"),
            walk_forward_result=raw.get("walk_forward_result"),
            rollback_condition=raw.get("rollback_condition"),
            affected_modules=list(raw.get("affected_modules") or []),
        )
    except KeyError as exc:
        raise ParameterRegistryError(f"missing parameter metadata field: {exc}") from exc
