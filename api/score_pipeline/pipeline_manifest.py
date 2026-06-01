from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_STAGE_IDS = (
    "collect_raw_data",
    "build_features",
    "calculate_scores",
    "macro_regime_distribution",
    "sector_asset_scoring",
    "risk_budget",
    "allocation",
    "rebalancing",
    "hard_constraint_filter",
    "order_candidate_generation",
    "audit_report",
)
AGGRESSIVE_FALLBACK_ACTIONS = {"BUY", "INCREASE_RISK", "AUTO_EXECUTE"}


class PipelineManifestError(ValueError):
    pass


@dataclass(frozen=True)
class PipelineStage:
    id: str
    layer: str
    required_inputs: tuple[str, ...]
    required_outputs: tuple[str, ...]
    required_validations: tuple[str, ...]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "PipelineStage":
        for field_name in ("id", "layer", "required_inputs", "required_outputs", "required_validations"):
            if field_name not in raw:
                raise PipelineManifestError(f"stage missing required field: {field_name}")
        return cls(
            id=_require_text(raw["id"], "stage.id"),
            layer=_require_text(raw["layer"], "stage.layer"),
            required_inputs=_require_string_tuple(raw["required_inputs"], "stage.required_inputs"),
            required_outputs=_require_string_tuple(raw["required_outputs"], "stage.required_outputs"),
            required_validations=_require_string_tuple(raw["required_validations"], "stage.required_validations"),
        )


@dataclass(frozen=True)
class PipelineManifest:
    version: int
    name: str
    execution_mode_default: str
    auto_execution_allowed: bool
    fallback_allowed_actions: tuple[str, ...]
    fallback_forbidden_actions: tuple[str, ...]
    stages: tuple[PipelineStage, ...]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "PipelineManifest":
        for field_name in ("version", "name", "stages", "fallback_policy", "auto_execution_allowed"):
            if field_name not in raw:
                raise PipelineManifestError(f"manifest missing required field: {field_name}")
        fallback_policy = raw["fallback_policy"]
        if not isinstance(fallback_policy, dict):
            raise PipelineManifestError("fallback_policy must be a mapping")
        stages = raw["stages"]
        if not isinstance(stages, list):
            raise PipelineManifestError("stages must be a list")
        allowed_actions = fallback_policy.get("allowed_actions")
        forbidden_actions = fallback_policy.get("forbidden_actions")
        return cls(
            version=_require_int(raw["version"], "version"),
            name=_require_text(raw["name"], "name"),
            execution_mode_default=_require_text(raw.get("execution_mode_default", ""), "execution_mode_default"),
            auto_execution_allowed=_require_bool(raw["auto_execution_allowed"], "auto_execution_allowed"),
            fallback_allowed_actions=_require_string_tuple(allowed_actions, "fallback_policy.allowed_actions"),
            fallback_forbidden_actions=_require_string_tuple(forbidden_actions, "fallback_policy.forbidden_actions"),
            stages=tuple(PipelineStage.from_mapping(stage) for stage in stages),
        )


def load_pipeline_manifest(path: str | Path) -> PipelineManifest:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PipelineManifestError("pipeline manifest must be a mapping")
    manifest = PipelineManifest.from_mapping(raw)
    validate_pipeline_manifest(manifest)
    return manifest


def validate_pipeline_manifest(manifest: PipelineManifest) -> None:
    stage_ids = [stage.id for stage in manifest.stages]
    duplicate_stage_ids = sorted(stage_id for stage_id in set(stage_ids) if stage_ids.count(stage_id) > 1)
    if duplicate_stage_ids:
        raise PipelineManifestError(f"duplicate stage ids: {duplicate_stage_ids}")

    missing_stage_ids = [stage_id for stage_id in REQUIRED_STAGE_IDS if stage_id not in stage_ids]
    if missing_stage_ids:
        raise PipelineManifestError(f"missing required stage ids: {missing_stage_ids}")

    if stage_ids[0] != "collect_raw_data":
        raise PipelineManifestError("collect_raw_data must be the first stage")
    if stage_ids[-1] != "audit_report":
        raise PipelineManifestError("audit_report must be the last stage")
    if stage_ids.index("hard_constraint_filter") > stage_ids.index("order_candidate_generation"):
        raise PipelineManifestError("hard_constraint_filter must run before order_candidate_generation")
    if manifest.auto_execution_allowed:
        raise PipelineManifestError("auto_execution_allowed must be false")

    allowed_actions = set(manifest.fallback_allowed_actions)
    forbidden_actions = set(manifest.fallback_forbidden_actions)
    overlapping_actions = sorted(allowed_actions & forbidden_actions)
    if overlapping_actions:
        raise PipelineManifestError(f"fallback actions cannot be both allowed and forbidden: {overlapping_actions}")
    aggressive_allowed_actions = sorted(allowed_actions & AGGRESSIVE_FALLBACK_ACTIONS)
    if aggressive_allowed_actions:
        raise PipelineManifestError(f"fallback allowed_actions contains aggressive actions: {aggressive_allowed_actions}")


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PipelineManifestError(f"{field_name} must be a non-empty string")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise PipelineManifestError(f"{field_name} must be a boolean")
    return value


def _require_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise PipelineManifestError(f"{field_name} must be an integer")
    return value


def _require_string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PipelineManifestError(f"{field_name} must be a list")
    for item in value:
        if not isinstance(item, str) or not item:
            raise PipelineManifestError(f"{field_name} must contain only non-empty strings")
    return tuple(value)
