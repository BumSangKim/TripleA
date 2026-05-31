from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Callable, Mapping, Sequence

from api.features.backtests.sector_component_attribution import calculate_sector_component_attribution
from api.features.backtests.sector_component_breakdown import (
    SectorComponentPeriodRecord,
    calculate_regime_stress_breakdown,
)
from api.features.backtests.sector_component_config import SectorComponentBacktestConfig
from api.features.backtests.sector_component_dataset import build_sector_component_snapshots
from api.features.backtests.sector_component_models import (
    SectorComponentAttributionRow,
    SectorComponentBacktestResult,
    SectorComponentMetricSummary,
    SectorComponentObservation,
    SectorComponentSensitivityResult,
    SectorComponentSnapshot,
    SectorComponentValidationWarning,
)
from api.features.backtests.sector_component_sensitivity import run_sector_component_sensitivity


@dataclass(frozen=True)
class SectorComponentReturnRecord:
    sector_id: str
    as_of_date: date
    forward_return: float
    available_at: datetime | None = None
    data_snapshot_id: str | None = None


@dataclass(frozen=True)
class SectorComponentRegimeRecord:
    sector_id: str
    as_of_date: date
    regime: str
    available_at: datetime | None = None
    data_snapshot_id: str | None = None


class SectorComponentRunnerError(ValueError):
    pass


def run_sector_component_backtest(
    config: SectorComponentBacktestConfig,
    observations: Sequence[SectorComponentObservation | Mapping[str, Any]],
    historical_returns: Sequence[SectorComponentReturnRecord | Mapping[str, Any]],
    *,
    macro_regime_records: Sequence[SectorComponentRegimeRecord | Mapping[str, Any]] = (),
    period_return_adjuster: Callable[[float], float] | None = None,
    data_quality_warning_threshold: float = 0.7,
) -> SectorComponentBacktestResult:
    normalized_observations = _coerce_observations(observations)
    normalized_returns = _coerce_returns(historical_returns)
    normalized_regimes = _coerce_regimes(macro_regime_records)

    if not normalized_observations:
        return _fallback_result(config, "SECTOR_COMPONENT_OBSERVATIONS_MISSING", "sector component observations are missing")

    decision_dates = _decision_dates(normalized_observations, normalized_returns)
    snapshots = build_sector_component_snapshots(
        normalized_observations,
        decision_dates,
        required_components=config.enabled_components,
        parameter_version=config.parameter_version,
        model_version=config.model_version,
    )
    if not snapshots:
        return _fallback_result(config, "SECTOR_COMPONENT_SNAPSHOTS_MISSING", "sector component snapshots could not be built")

    forward_returns = _forward_returns_by_sector_date(normalized_returns, period_return_adjuster)
    baseline_weights = config.component_weight_grid[0].weights
    attribution_rows = _attribution_rows(snapshots, baseline_weights)
    metric_summary = _metric_summary(config, snapshots, attribution_rows, forward_returns)
    sensitivity_results = _sensitivity_results(config, snapshots, forward_returns)
    breakdowns = _breakdowns(config, snapshots, attribution_rows, forward_returns, normalized_regimes)
    warnings = _aggregate_warnings(
        config=config,
        snapshots=snapshots,
        attribution_rows=attribution_rows,
        metric_summary=metric_summary,
        sensitivity_results=sensitivity_results,
        breakdowns=breakdowns,
        observations=normalized_observations,
        forward_returns=forward_returns,
        data_quality_warning_threshold=data_quality_warning_threshold,
    )
    sector_id = _result_sector_id(snapshots)
    latest_snapshot = max(snapshots, key=lambda item: (item.as_of_date, item.available_at, item.data_snapshot_id))
    status = config.fallback_policy if warnings else "OK"
    reason_codes = _reason_codes(warnings, "SECTOR_COMPONENT_BACKTEST_RUNNER_COMPLETED")
    return SectorComponentBacktestResult(
        sector_id=sector_id,
        as_of_date=latest_snapshot.as_of_date,
        available_at=latest_snapshot.available_at,
        parameter_version=config.parameter_version,
        model_version=config.model_version,
        data_snapshot_id=f"sector-component-backtest:{sector_id}:{latest_snapshot.as_of_date.isoformat()}:{config.parameter_version}",
        metric_summaries=(metric_summary,),
        attribution_rows=attribution_rows,
        sensitivity_results=sensitivity_results,
        regime_breakdowns=tuple(item.to_dict() for item in breakdowns),
        status=status,
        reason_codes=reason_codes,
        warnings=warnings,
    )


def _coerce_observations(
    observations: Sequence[SectorComponentObservation | Mapping[str, Any]],
) -> tuple[SectorComponentObservation, ...]:
    normalized: list[SectorComponentObservation] = []
    for raw in observations:
        if isinstance(raw, SectorComponentObservation):
            normalized.append(raw)
            continue
        normalized.append(
            SectorComponentObservation(
                sector_id=_required_text(raw, "sector_id"),
                component_name=_required_text(raw, "component_name"),
                score=_optional_float(raw.get("score")),
                as_of_date=_coerce_date(raw.get("as_of_date")),
                available_at=_coerce_datetime(raw.get("available_at")),
                parameter_version=_required_text(raw, "parameter_version"),
                model_version=_required_text(raw, "model_version"),
                data_snapshot_id=_required_text(raw, "data_snapshot_id"),
                reason_codes=tuple(raw.get("reason_codes", ())),
                confidence=float(raw.get("confidence", 1.0)),
                data_quality=float(raw.get("data_quality", raw.get("quality_score", 1.0))),
                source=raw.get("source"),
            )
        )
    return tuple(sorted(normalized, key=lambda item: (item.sector_id, item.as_of_date, item.component_name, item.available_at, item.data_snapshot_id)))


def _coerce_returns(
    records: Sequence[SectorComponentReturnRecord | Mapping[str, Any]],
) -> tuple[SectorComponentReturnRecord, ...]:
    normalized: list[SectorComponentReturnRecord] = []
    for raw in records:
        if isinstance(raw, SectorComponentReturnRecord):
            normalized.append(raw)
            continue
        if "forward_return" in raw:
            forward_return = raw["forward_return"]
        elif "period_return" in raw:
            forward_return = raw["period_return"]
        else:
            raise SectorComponentRunnerError("historical return records require forward_return or period_return")
        normalized.append(
            SectorComponentReturnRecord(
                sector_id=_required_text(raw, "sector_id"),
                as_of_date=_coerce_date(raw.get("as_of_date")),
                forward_return=float(forward_return),
                available_at=_coerce_optional_datetime(raw.get("available_at")),
                data_snapshot_id=raw.get("data_snapshot_id"),
            )
        )
    return tuple(sorted(normalized, key=lambda item: (item.sector_id, item.as_of_date, item.forward_return, item.data_snapshot_id or "")))


def _coerce_regimes(
    records: Sequence[SectorComponentRegimeRecord | Mapping[str, Any]],
) -> tuple[SectorComponentRegimeRecord, ...]:
    normalized: list[SectorComponentRegimeRecord] = []
    for raw in records:
        if isinstance(raw, SectorComponentRegimeRecord):
            normalized.append(raw)
            continue
        normalized.append(
            SectorComponentRegimeRecord(
                sector_id=_required_text(raw, "sector_id"),
                as_of_date=_coerce_date(raw.get("as_of_date")),
                regime=_required_text(raw, "regime"),
                available_at=_coerce_optional_datetime(raw.get("available_at")),
                data_snapshot_id=raw.get("data_snapshot_id"),
            )
        )
    return tuple(sorted(normalized, key=lambda item: (item.sector_id, item.as_of_date, item.regime, item.data_snapshot_id or "")))


def _decision_dates(
    observations: Sequence[SectorComponentObservation],
    returns: Sequence[SectorComponentReturnRecord],
) -> tuple[date, ...]:
    dates = {item.as_of_date for item in observations}
    dates.update(item.as_of_date for item in returns)
    return tuple(sorted(dates))


def _forward_returns_by_sector_date(
    records: Sequence[SectorComponentReturnRecord],
    adjuster: Callable[[float], float] | None,
) -> dict[tuple[str, date], float]:
    forward_returns: dict[tuple[str, date], float] = {}
    for record in records:
        value = float(record.forward_return)
        if adjuster is not None:
            value = float(adjuster(value))
        forward_returns[(record.sector_id, record.as_of_date)] = value
    return forward_returns


def _attribution_rows(
    snapshots: Sequence[SectorComponentSnapshot],
    component_weights: Mapping[str, float],
) -> tuple[SectorComponentAttributionRow, ...]:
    rows: list[SectorComponentAttributionRow] = []
    previous_by_sector: dict[str, SectorComponentSnapshot] = {}
    for snapshot in sorted(snapshots, key=lambda item: (item.sector_id, item.as_of_date, item.data_snapshot_id)):
        rows.extend(
            calculate_sector_component_attribution(
                snapshot,
                component_weights,
                previous_snapshot=previous_by_sector.get(snapshot.sector_id),
            )
        )
        previous_by_sector[snapshot.sector_id] = snapshot
    return tuple(rows)


def _metric_summary(
    config: SectorComponentBacktestConfig,
    snapshots: Sequence[SectorComponentSnapshot],
    attribution_rows: Sequence[SectorComponentAttributionRow],
    forward_returns: Mapping[tuple[str, date], float],
) -> SectorComponentMetricSummary:
    rows_by_snapshot = _rows_by_snapshot(attribution_rows)
    period_values: list[float] = []
    warnings: list[SectorComponentValidationWarning] = []
    for snapshot in sorted(snapshots, key=lambda item: (item.sector_id, item.as_of_date, item.data_snapshot_id)):
        rows = rows_by_snapshot.get(snapshot.data_snapshot_id, ())
        score = sum(row.weighted_contribution for row in rows if row.weighted_contribution is not None)
        forward_return = forward_returns.get((snapshot.sector_id, snapshot.as_of_date))
        if forward_return is None:
            warnings.append(_warning_from_snapshot(snapshot, "HISTORICAL_RETURN_MISSING", "historical return is missing"))
            continue
        period_values.append(score * forward_return)

    latest_snapshot = max(snapshots, key=lambda item: (item.as_of_date, item.available_at, item.data_snapshot_id))
    return SectorComponentMetricSummary(
        sector_id=_result_sector_id(snapshots),
        as_of_date=latest_snapshot.as_of_date,
        available_at=latest_snapshot.available_at,
        parameter_version=config.parameter_version,
        model_version=config.model_version,
        data_snapshot_id=f"sector-component-metric:{latest_snapshot.as_of_date.isoformat()}:{config.parameter_version}",
        total_return=round(sum(period_values), 8) if period_values else None,
        annualized_return=None,
        max_drawdown=round(_max_drawdown(period_values), 8) if period_values else None,
        volatility=round(_volatility(period_values), 8) if period_values else None,
        hit_rate=_hit_rate(period_values) if period_values else None,
        observation_count=len(period_values),
        reason_codes=("SECTOR_COMPONENT_BACKTEST_METRIC_SUMMARY",),
        warnings=tuple(warnings),
    )


def _sensitivity_results(
    config: SectorComponentBacktestConfig,
    snapshots: Sequence[SectorComponentSnapshot],
    forward_returns: Mapping[tuple[str, date], float],
) -> tuple[SectorComponentSensitivityResult, ...]:
    all_results: list[SectorComponentSensitivityResult] = []
    for sector_id in sorted({snapshot.sector_id for snapshot in snapshots}):
        sector_snapshots = tuple(snapshot for snapshot in snapshots if snapshot.sector_id == sector_id)
        sector_returns = {as_of_date: value for (return_sector_id, as_of_date), value in forward_returns.items() if return_sector_id == sector_id}
        all_results.extend(run_sector_component_sensitivity(sector_snapshots, config.component_weight_grid, forward_returns=sector_returns))
    return tuple(sorted(all_results, key=lambda item: (item.sector_id, item.parameter_set_id, item.as_of_date)))


def _breakdowns(
    config: SectorComponentBacktestConfig,
    snapshots: Sequence[SectorComponentSnapshot],
    attribution_rows: Sequence[SectorComponentAttributionRow],
    forward_returns: Mapping[tuple[str, date], float],
    regimes: Sequence[SectorComponentRegimeRecord],
):
    rows_by_snapshot = _rows_by_snapshot(attribution_rows)
    records: list[SectorComponentPeriodRecord] = []
    for snapshot in sorted(snapshots, key=lambda item: (item.sector_id, item.as_of_date, item.data_snapshot_id)):
        rows = rows_by_snapshot.get(snapshot.data_snapshot_id, ())
        contributions = {row.component_name: float(row.weighted_contribution or 0.0) for row in rows}
        records.append(
            SectorComponentPeriodRecord(
                sector_id=snapshot.sector_id,
                as_of_date=snapshot.as_of_date,
                available_at=snapshot.available_at,
                period_return=float(forward_returns.get((snapshot.sector_id, snapshot.as_of_date), 0.0)),
                component_contributions=contributions,
                confidence=_average([row.confidence for row in snapshot.observations]),
                data_quality=_average([row.data_quality for row in snapshot.observations]),
                reason_codes=("SECTOR_COMPONENT_BACKTEST_PERIOD",),
                warnings=tuple(snapshot.warnings),
            )
        )
    regime_labels = {(record.sector_id, record.as_of_date): record.regime for record in regimes}
    results = []
    for sector_id in sorted({record.sector_id for record in records}):
        sector_records = tuple(record for record in records if record.sector_id == sector_id)
        sector_regimes = {as_of_date: regime for (regime_sector_id, as_of_date), regime in regime_labels.items() if regime_sector_id == sector_id}
        results.extend(calculate_regime_stress_breakdown(sector_records, regime_labels=sector_regimes, stress_periods=config.stress_periods))
    return tuple(results)


def _aggregate_warnings(
    *,
    config: SectorComponentBacktestConfig,
    snapshots: Sequence[SectorComponentSnapshot],
    attribution_rows: Sequence[SectorComponentAttributionRow],
    metric_summary: SectorComponentMetricSummary,
    sensitivity_results: Sequence[SectorComponentSensitivityResult],
    breakdowns: Sequence[Any],
    observations: Sequence[SectorComponentObservation],
    forward_returns: Mapping[tuple[str, date], float],
    data_quality_warning_threshold: float,
) -> tuple[SectorComponentValidationWarning, ...]:
    warnings: list[SectorComponentValidationWarning] = []
    warnings.extend(_config_warnings(config, snapshots))
    for snapshot in snapshots:
        warnings.extend(snapshot.warnings)
        if (snapshot.sector_id, snapshot.as_of_date) not in forward_returns:
            warnings.append(_warning_from_snapshot(snapshot, "HISTORICAL_RETURN_MISSING", "historical return is missing"))
    for row in attribution_rows:
        warnings.extend(row.warnings)
    warnings.extend(metric_summary.warnings)
    for result in sensitivity_results:
        warnings.extend(result.warnings)
        warnings.extend(result.metric_summary.warnings)
    for breakdown in breakdowns:
        warnings.extend(breakdown.warnings)
    for observation in observations:
        warnings.extend(observation.warnings)
        if observation.data_quality < data_quality_warning_threshold:
            warnings.append(
                SectorComponentValidationWarning(
                    sector_id=observation.sector_id,
                    component_name=observation.component_name,
                    as_of_date=observation.as_of_date,
                    available_at=observation.available_at,
                    parameter_version=observation.parameter_version,
                    model_version=observation.model_version,
                    data_snapshot_id=observation.data_snapshot_id,
                    reason_codes=("REVIEW_REQUIRED",),
                    warnings=("SECTOR_COMPONENT_LOW_DATA_QUALITY",),
                    code="SECTOR_COMPONENT_LOW_DATA_QUALITY",
                    message="sector component data quality is below review threshold",
                )
            )
    return _dedupe_warnings(warnings)


def _config_warnings(
    config: SectorComponentBacktestConfig,
    snapshots: Sequence[SectorComponentSnapshot],
) -> tuple[SectorComponentValidationWarning, ...]:
    if not config.validation_warnings:
        return ()
    latest_snapshot = max(snapshots, key=lambda item: (item.as_of_date, item.available_at, item.data_snapshot_id))
    return tuple(
        SectorComponentValidationWarning(
            sector_id=latest_snapshot.sector_id,
            as_of_date=latest_snapshot.as_of_date,
            available_at=latest_snapshot.available_at,
            parameter_version=config.parameter_version,
            model_version=config.model_version,
            data_snapshot_id=latest_snapshot.data_snapshot_id,
            reason_codes=("REVIEW_REQUIRED",),
            warnings=(warning.code,),
            code=warning.code,
            message=warning.message,
            fallback_state=warning.fallback_state,
        )
        for warning in config.validation_warnings
    )


def _fallback_result(config: SectorComponentBacktestConfig, code: str, message: str) -> SectorComponentBacktestResult:
    as_of_date = date(1970, 1, 1)
    available_at = datetime.combine(as_of_date, time.min, tzinfo=UTC)
    warning = SectorComponentValidationWarning(
        sector_id="UNKNOWN",
        as_of_date=as_of_date,
        available_at=available_at,
        parameter_version=config.parameter_version,
        model_version=config.model_version,
        data_snapshot_id="sector-component-backtest:missing-input",
        reason_codes=("REVIEW_REQUIRED",),
        warnings=(code,),
        code=code,
        message=message,
        fallback_state=config.fallback_policy,
    )
    return SectorComponentBacktestResult(
        sector_id="UNKNOWN",
        as_of_date=as_of_date,
        available_at=available_at,
        parameter_version=config.parameter_version,
        model_version=config.model_version,
        data_snapshot_id="sector-component-backtest:missing-input",
        status=config.fallback_policy,
        reason_codes=("REVIEW_REQUIRED", code),
        warnings=(warning,),
    )


def _rows_by_snapshot(
    attribution_rows: Sequence[SectorComponentAttributionRow],
) -> dict[str, tuple[SectorComponentAttributionRow, ...]]:
    grouped: dict[str, list[SectorComponentAttributionRow]] = {}
    for row in attribution_rows:
        grouped.setdefault(row.data_snapshot_id, []).append(row)
    return {key: tuple(sorted(value, key=lambda item: item.component_name)) for key, value in grouped.items()}


def _result_sector_id(snapshots: Sequence[SectorComponentSnapshot]) -> str:
    sector_ids = sorted({snapshot.sector_id for snapshot in snapshots})
    if not sector_ids:
        return "UNKNOWN"
    if len(sector_ids) == 1:
        return sector_ids[0]
    return "MULTI_SECTOR"


def _reason_codes(warnings: Sequence[SectorComponentValidationWarning], base: str) -> tuple[str, ...]:
    values = {base}
    for warning in warnings:
        values.update(warning.reason_codes)
        values.update(warning.warnings)
    if warnings:
        values.add("REVIEW_REQUIRED")
    return tuple(sorted(values))


def _dedupe_warnings(warnings: Sequence[SectorComponentValidationWarning]) -> tuple[SectorComponentValidationWarning, ...]:
    by_key: dict[tuple[Any, ...], SectorComponentValidationWarning] = {}
    for warning in warnings:
        key = (
            warning.sector_id,
            warning.component_name or "",
            warning.as_of_date,
            warning.available_at,
            warning.parameter_version,
            warning.model_version,
            warning.data_snapshot_id,
            warning.code,
            warning.message,
        )
        by_key[key] = warning
    return tuple(by_key[key] for key in sorted(by_key))


def _warning_from_snapshot(
    snapshot: SectorComponentSnapshot,
    code: str,
    message: str,
    *,
    component_name: str | None = None,
) -> SectorComponentValidationWarning:
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
        message=message,
    )


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


def _average(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(float(value) for value in values) / len(values)


def _required_text(raw: Mapping[str, Any], field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SectorComponentRunnerError(f"{field_name} must be non-empty text")
    return value.strip()


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _coerce_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise SectorComponentRunnerError("date value must be a date or ISO date string")


def _coerce_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    return _coerce_datetime(value)


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise SectorComponentRunnerError("datetime value must be a datetime or ISO datetime string")
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result
