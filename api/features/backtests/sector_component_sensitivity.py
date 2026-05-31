from __future__ import annotations

import statistics
from datetime import date
from typing import Mapping, Sequence

from api.features.backtests.sector_component_attribution import (
    SectorComponentAttributionError,
    calculate_sector_component_attribution,
)
from api.features.backtests.sector_component_config import SectorComponentWeightSet
from api.features.backtests.sector_component_models import (
    SectorComponentMetricSummary,
    SectorComponentSensitivityResult,
    SectorComponentSnapshot,
    SectorComponentValidationWarning,
)


class SectorComponentSensitivityError(ValueError):
    pass


def run_sector_component_sensitivity(
    snapshots: Sequence[SectorComponentSnapshot],
    weight_grid: Sequence[SectorComponentWeightSet],
    *,
    forward_returns: Mapping[date, float] | None = None,
    fragility_threshold: float = 0.05,
) -> tuple[SectorComponentSensitivityResult, ...]:
    if not snapshots:
        raise SectorComponentSensitivityError("snapshots must not be empty")
    if not weight_grid:
        raise SectorComponentSensitivityError("weight_grid must not be empty")

    ordered_snapshots = tuple(sorted(snapshots, key=lambda item: (item.sector_id, item.as_of_date, item.data_snapshot_id)))
    results = [_evaluate_weight_set(ordered_snapshots, weight_set, forward_returns or {}) for weight_set in sorted(weight_grid, key=lambda item: item.parameter_set_id)]
    ranked = _rank_results(results)
    if _performance_dispersion(ranked) > fragility_threshold:
        ranked = [_append_fragility_warning(result) for result in ranked]
    return tuple(ranked)


def _evaluate_weight_set(
    snapshots: Sequence[SectorComponentSnapshot],
    weight_set: SectorComponentWeightSet,
    forward_returns: Mapping[date, float],
) -> SectorComponentSensitivityResult:
    score_values: list[float] = []
    period_values: list[float] = []
    warnings: list[SectorComponentValidationWarning] = []
    for snapshot in snapshots:
        try:
            attribution_rows = calculate_sector_component_attribution(snapshot, weight_set.weights)
        except SectorComponentAttributionError as exc:
            raise SectorComponentSensitivityError(str(exc)) from exc
        warnings.extend(snapshot.warnings)
        for row in attribution_rows:
            warnings.extend(row.warnings)
        valid_contributions = [row.weighted_contribution for row in attribution_rows if row.weighted_contribution is not None]
        weighted_score = sum(valid_contributions)
        score_values.append(weighted_score)
        if snapshot.as_of_date in forward_returns:
            period_values.append(weighted_score * float(forward_returns[snapshot.as_of_date]))

    metric_values = period_values if period_values else score_values
    total_return = sum(metric_values)
    metric_summary = SectorComponentMetricSummary(
        sector_id=snapshots[-1].sector_id,
        as_of_date=snapshots[-1].as_of_date,
        available_at=snapshots[-1].available_at,
        parameter_version=snapshots[-1].parameter_version,
        model_version=snapshots[-1].model_version,
        data_snapshot_id=snapshots[-1].data_snapshot_id,
        total_return=round(total_return, 8),
        max_drawdown=round(_max_drawdown(metric_values), 8),
        volatility=round(_volatility(metric_values), 8),
        hit_rate=_hit_rate(period_values) if period_values else None,
        observation_count=len(metric_values),
        reason_codes=("PARAMETER_SENSITIVITY_METRIC_SUMMARY",),
        warnings=tuple(warnings),
    )
    stability = max(0.0, min(1.0, 1.0 - _volatility(score_values)))
    return SectorComponentSensitivityResult(
        sector_id=snapshots[-1].sector_id,
        as_of_date=snapshots[-1].as_of_date,
        available_at=snapshots[-1].available_at,
        parameter_version=snapshots[-1].parameter_version,
        model_version=snapshots[-1].model_version,
        data_snapshot_id=snapshots[-1].data_snapshot_id,
        parameter_set_id=weight_set.parameter_set_id,
        component_weights=dict(sorted(weight_set.weights.items())),
        metric_summary=metric_summary,
        stability_score=round(stability, 8),
        approved_for_production=False,
        reason_codes=("PARAMETER_SENSITIVITY_DIAGNOSTIC",),
        warnings=tuple(warnings),
    )


def _rank_results(results: list[SectorComponentSensitivityResult]) -> list[SectorComponentSensitivityResult]:
    ordered = sorted(
        results,
        key=lambda item: (item.metric_summary.total_return if item.metric_summary.total_return is not None else float("-inf"), item.parameter_set_id),
        reverse=True,
    )
    ranked: list[SectorComponentSensitivityResult] = []
    for index, result in enumerate(ordered, start=1):
        ranked.append(
            SectorComponentSensitivityResult(
                sector_id=result.sector_id,
                as_of_date=result.as_of_date,
                available_at=result.available_at,
                parameter_version=result.parameter_version,
                model_version=result.model_version,
                data_snapshot_id=result.data_snapshot_id,
                parameter_set_id=result.parameter_set_id,
                component_weights=result.component_weights,
                metric_summary=result.metric_summary,
                stability_score=result.stability_score,
                rank=index,
                approved_for_production=False,
                reason_codes=result.reason_codes,
                warnings=result.warnings,
            )
        )
    return sorted(ranked, key=lambda item: item.parameter_set_id)


def _append_fragility_warning(result: SectorComponentSensitivityResult) -> SectorComponentSensitivityResult:
    warning = SectorComponentValidationWarning(
        sector_id=result.sector_id,
        as_of_date=result.as_of_date,
        available_at=result.available_at,
        parameter_version=result.parameter_version,
        model_version=result.model_version,
        data_snapshot_id=result.data_snapshot_id,
        reason_codes=("REVIEW_REQUIRED",),
        warnings=("PARAMETER_FRAGILITY",),
        code="PARAMETER_FRAGILITY",
        message="small parameter-grid changes produced high metric dispersion",
    )
    return SectorComponentSensitivityResult(
        sector_id=result.sector_id,
        as_of_date=result.as_of_date,
        available_at=result.available_at,
        parameter_version=result.parameter_version,
        model_version=result.model_version,
        data_snapshot_id=result.data_snapshot_id,
        parameter_set_id=result.parameter_set_id,
        component_weights=result.component_weights,
        metric_summary=result.metric_summary,
        stability_score=result.stability_score,
        rank=result.rank,
        approved_for_production=False,
        reason_codes=(*result.reason_codes, "PARAMETER_FRAGILITY_REVIEW_REQUIRED"),
        warnings=(*result.warnings, warning),
    )


def _performance_dispersion(results: Sequence[SectorComponentSensitivityResult]) -> float:
    values = [result.metric_summary.total_return for result in results if result.metric_summary.total_return is not None]
    return max(values) - min(values) if values else 0.0


def _max_drawdown(values: Sequence[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in values:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return max_drawdown


def _volatility(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return statistics.pstdev(values)


def _hit_rate(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if value >= 0) / len(values)

