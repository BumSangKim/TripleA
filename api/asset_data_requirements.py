from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .asset_universe_loader import PROJECT_ROOT


DEFAULT_DATA_REQUIREMENTS_PATH = PROJECT_ROOT / "config" / "asset_data_requirements.yaml"


class AssetDataRequirementError(ValueError):
    pass


@dataclass(frozen=True)
class DataRequirementDefinition:
    key: str
    description: str
    required_for_score: bool
    stale_after_days: int | None
    review_required: bool = False


def load_data_requirement_definitions(
    path: str | Path | None = None,
) -> dict[str, DataRequirementDefinition]:
    requirement_path = Path(path) if path is not None else DEFAULT_DATA_REQUIREMENTS_PATH
    raw = yaml.safe_load(requirement_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise AssetDataRequirementError("data requirement config must be an object")
    requirements = raw.get("requirements")
    if not isinstance(requirements, dict) or not requirements:
        raise AssetDataRequirementError("requirements must be a non-empty object")
    return {
        key: _definition(key, value)
        for key, value in requirements.items()
    }


def validate_data_requirement_keys(
    keys: list[str],
    *,
    enabled: bool,
    role: str,
    definitions: dict[str, DataRequirementDefinition] | None = None,
) -> list[str]:
    definitions = definitions or load_data_requirement_definitions()
    issues: list[str] = []
    for key in keys:
        definition = definitions.get(key)
        if definition is None:
            issues.append(f"unknown data requirement: {key}")
            continue
        if definition.review_required:
            if enabled or role != "watchlist":
                issues.append(f"review-required data requirement is allowed only for inactive watchlist assets: {key}")
            else:
                issues.append(f"review-required data requirement retained for inactive watchlist asset: {key}")
    return issues


def _definition(key: str, raw: Any) -> DataRequirementDefinition:
    if not isinstance(key, str) or not key.strip():
        raise AssetDataRequirementError("data requirement key must be a non-empty string")
    if not isinstance(raw, dict):
        raise AssetDataRequirementError(f"{key} must be an object")
    description = raw.get("description")
    if not isinstance(description, str) or not description.strip():
        raise AssetDataRequirementError(f"{key}.description must be a non-empty string")
    required_for_score = raw.get("required_for_score")
    if not isinstance(required_for_score, bool):
        raise AssetDataRequirementError(f"{key}.required_for_score must be a boolean")
    stale_after_days = raw.get("stale_after_days")
    if stale_after_days is not None:
        if isinstance(stale_after_days, bool) or not isinstance(stale_after_days, int) or stale_after_days <= 0:
            raise AssetDataRequirementError(f"{key}.stale_after_days must be a positive integer or null")
    review_required = raw.get("review_required", False)
    if not isinstance(review_required, bool):
        raise AssetDataRequirementError(f"{key}.review_required must be a boolean")
    return DataRequirementDefinition(
        key=key.strip(),
        description=description.strip(),
        required_for_score=required_for_score,
        stale_after_days=stale_after_days,
        review_required=review_required,
    )
