from __future__ import annotations

from typing import Mapping

from api.features.backtests.sector_component_models import (
    SectorComponentAttributionRow,
    SectorComponentObservation,
    SectorComponentSnapshot,
    SectorComponentValidationWarning,
)


class SectorComponentAttributionError(ValueError):
    pass


def calculate_sector_component_attribution(
    snapshot: SectorComponentSnapshot,
    component_weights: Mapping[str, float],
    *,
    previous_snapshot: SectorComponentSnapshot | None = None,
) -> tuple[SectorComponentAttributionRow, ...]:
    weights = _validate_weights(component_weights)
    current = {row.component_name: row for row in snapshot.observations}
    previous = {row.component_name: row for row in previous_snapshot.observations} if previous_snapshot else {}
    raw_rows: list[tuple[str, float | None, SectorComponentAttributionRow]] = []

    for component_name in sorted(weights):
        weight = weights[component_name]
        observation = current.get(component_name)
        previous_observation = previous.get(component_name)
        warnings: list[SectorComponentValidationWarning] = []
        reason_codes = ["SECTOR_COMPONENT_ATTRIBUTION_DIAGNOSTIC"]
        score = None if observation is None else observation.score
        previous_score = None if previous_observation is None else previous_observation.score
        contribution: float | None = None

        if observation is None or score is None:
            warnings.append(_warning(snapshot, "COMPONENT_ATTRIBUTION_INPUT_MISSING", component_name))
            reason_codes.append("REVIEW_REQUIRED")
        elif not 0.0 <= float(score) <= 1.0:
            warnings.extend(observation.warnings)
            warnings.append(_warning(snapshot, "COMPONENT_ATTRIBUTION_SCORE_INVALID", component_name))
            reason_codes.append("REVIEW_REQUIRED")
        else:
            warnings.extend(observation.warnings)
            contribution = float(score) * weight

        score_change = None
        if score is not None and previous_score is not None:
            score_change = float(score) - float(previous_score)

        raw_rows.append(
            (
                component_name,
                contribution,
                SectorComponentAttributionRow(
                    sector_id=snapshot.sector_id,
                    component_name=component_name,
                    as_of_date=snapshot.as_of_date,
                    available_at=snapshot.available_at,
                    parameter_version=snapshot.parameter_version,
                    model_version=snapshot.model_version,
                    data_snapshot_id=snapshot.data_snapshot_id,
                    score=score,
                    weight=weight,
                    weighted_contribution=contribution,
                    contribution_share=None,
                    previous_score=previous_score,
                    score_change=score_change,
                    reason_codes=tuple(reason_codes),
                    warnings=tuple(warnings),
                ),
            )
        )

    total_contribution = sum(contribution for _, contribution, _ in raw_rows if contribution is not None)
    if total_contribution <= 0:
        return tuple(row for _, _, row in raw_rows)
    return tuple(_with_share(row, None if contribution is None else contribution / total_contribution) for _, contribution, row in raw_rows)


def _validate_weights(component_weights: Mapping[str, float]) -> dict[str, float]:
    if not component_weights:
        raise SectorComponentAttributionError("component_weights must not be empty")
    weights = {str(component): float(weight) for component, weight in component_weights.items()}
    if any(weight < 0 for weight in weights.values()):
        raise SectorComponentAttributionError("component_weights must be non-negative")
    total = sum(weights.values())
    if abs(total - 1.0) > 0.000001:
        raise SectorComponentAttributionError("component_weights must sum to 1.0")
    return weights


def _with_share(row: SectorComponentAttributionRow, contribution_share: float | None) -> SectorComponentAttributionRow:
    return SectorComponentAttributionRow(
        sector_id=row.sector_id,
        component_name=row.component_name,
        as_of_date=row.as_of_date,
        available_at=row.available_at,
        parameter_version=row.parameter_version,
        model_version=row.model_version,
        data_snapshot_id=row.data_snapshot_id,
        score=row.score,
        weight=row.weight,
        weighted_contribution=row.weighted_contribution,
        contribution_share=contribution_share,
        previous_score=row.previous_score,
        score_change=row.score_change,
        reason_codes=row.reason_codes,
        warnings=row.warnings,
    )


def _warning(snapshot: SectorComponentSnapshot, code: str, component_name: str) -> SectorComponentValidationWarning:
    return SectorComponentValidationWarning(
        sector_id=snapshot.sector_id,
        component_name=component_name,
        as_of_date=snapshot.as_of_date,
        available_at=snapshot.available_at,
        parameter_version=snapshot.parameter_version,
        model_version=snapshot.model_version,
        data_snapshot_id=snapshot.data_snapshot_id,
        reason_codes=("REVIEW_REQUIRED",),
        warnings=(code,),
        code=code,
        message=f"{component_name} attribution requires review",
    )

