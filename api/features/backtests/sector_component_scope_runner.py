from __future__ import annotations

from datetime import date
from typing import Any, Callable, Mapping, Sequence

from api.features.backtests.sector_component_models import (
    CONSERVATIVE_FALLBACK_STATES,
    SectorComponentBacktestResult,
    SectorComponentValidationWarning,
)
from api.features.backtests.sector_component_portfolios import (
    SectorComponentSectorPortfolio,
    enabled_sector_component_portfolios,
)
from api.features.backtests.sector_component_runner import run_sector_component_backtest
from api.features.backtests.sector_component_scope import (
    SectorComponentComparisonRow,
    SectorComponentScope,
    SectorComponentScopedBacktestResult,
)


SectorComponentRunner = Callable[..., SectorComponentBacktestResult]


def run_sector_component_scope_backtest(
    config: Any,
    observations: Sequence[Any],
    returns: Sequence[Any],
    regimes: Sequence[Any],
    portfolios: Sequence[SectorComponentSectorPortfolio],
    scope: SectorComponentScope,
    *,
    component_runner: SectorComponentRunner = run_sector_component_backtest,
) -> SectorComponentScopedBacktestResult:
    selected_portfolios = _select_portfolios(portfolios, scope)
    sector_results: list[SectorComponentBacktestResult] = []
    comparison_rows: list[SectorComponentComparisonRow] = []
    warnings: list[SectorComponentValidationWarning] = []
    for portfolio in selected_portfolios:
        result = component_runner(
            config,
            _filter_sector(observations, portfolio.sector_id),
            _filter_sector(returns, portfolio.sector_id),
            macro_regime_records=_filter_sector(regimes, portfolio.sector_id),
        )
        if result.sector_id == "MULTI_SECTOR":
            raise ValueError("sector scope child result must not be MULTI_SECTOR")
        sector_results.append(result)
        portfolio_warnings = _portfolio_warnings(portfolio, result)
        warnings.extend(result.warnings)
        warnings.extend(portfolio_warnings)
        comparison_rows.append(_comparison_row(portfolio, result, portfolio_warning_count=len(portfolio_warnings)))

    status = _aggregate_status(config, sector_results, warnings)
    latest = _latest_result(sector_results)
    reason_codes = _reason_codes(selected_portfolios, sector_results, warnings)
    return SectorComponentScopedBacktestResult(
        sector_scope=scope,
        parameter_version=_config_text(config, "parameter_version", "sector_component_backtest_unknown"),
        model_version=_config_text(config, "model_version", "sector_component_scope_runner"),
        data_snapshot_id=_scope_snapshot_id(scope, latest, config),
        status=status,
        comparison_rows=tuple(comparison_rows),
        sector_results=tuple(sector_results),
        warnings=tuple(warnings),
        reason_codes=reason_codes,
    )


def _select_portfolios(
    portfolios: Sequence[SectorComponentSectorPortfolio],
    scope: SectorComponentScope,
) -> tuple[SectorComponentSectorPortfolio, ...]:
    enabled = enabled_sector_component_portfolios(portfolios)
    if scope.mode == "all":
        if not enabled:
            raise ValueError("no enabled sector portfolios")
        return enabled
    selected = tuple(portfolio for portfolio in enabled if portfolio.sector_id == scope.sector_id)
    if not selected:
        raise ValueError(f"sector portfolio not enabled or unknown: {scope.sector_id}")
    return selected


def _filter_sector(items: Sequence[Any], sector_id: str) -> tuple[Any, ...]:
    return tuple(item for item in items if _sector_id(item) == sector_id)


def _sector_id(item: Any) -> str | None:
    if isinstance(item, Mapping):
        value = item.get("sector_id")
    else:
        value = getattr(item, "sector_id", None)
    return str(value).strip().upper() if value else None


def _comparison_row(
    portfolio: SectorComponentSectorPortfolio,
    result: SectorComponentBacktestResult,
    *,
    portfolio_warning_count: int,
) -> SectorComponentComparisonRow:
    metric = result.metric_summaries[0] if result.metric_summaries else None
    reason_codes = tuple(sorted({*portfolio.reason_codes, *result.reason_codes}))
    return SectorComponentComparisonRow(
        sector_id=portfolio.sector_id,
        display_name=portfolio.display_name,
        portfolio_id=portfolio.portfolio_id,
        status=result.status,
        total_return=None if metric is None else metric.total_return,
        max_drawdown=None if metric is None else metric.max_drawdown,
        volatility=None if metric is None else metric.volatility,
        hit_rate=None if metric is None else metric.hit_rate,
        observation_count=0 if metric is None else metric.observation_count,
        warning_count=len(result.warnings) + portfolio_warning_count,
        reason_codes=reason_codes,
    )


def _portfolio_warnings(
    portfolio: SectorComponentSectorPortfolio,
    result: SectorComponentBacktestResult,
) -> tuple[SectorComponentValidationWarning, ...]:
    return tuple(
        SectorComponentValidationWarning(
            sector_id=portfolio.sector_id,
            as_of_date=result.as_of_date,
            available_at=result.available_at,
            parameter_version=result.parameter_version,
            model_version=result.model_version,
            data_snapshot_id=result.data_snapshot_id,
            reason_codes=("REVIEW_REQUIRED",),
            warnings=(warning,),
            code=warning.split(":", 1)[0],
            message=warning,
        )
        for warning in portfolio.warnings
    )


def _aggregate_status(
    config: Any,
    results: Sequence[SectorComponentBacktestResult],
    warnings: Sequence[SectorComponentValidationWarning],
) -> str:
    if results and all(result.status == "OK" for result in results) and not warnings:
        return "OK"
    fallback = _config_text(config, "fallback_policy", "REVIEW_REQUIRED")
    return fallback if fallback in CONSERVATIVE_FALLBACK_STATES else "REVIEW_REQUIRED"


def _latest_result(results: Sequence[SectorComponentBacktestResult]) -> SectorComponentBacktestResult | None:
    if not results:
        return None
    return max(results, key=lambda item: (item.as_of_date, item.available_at, item.data_snapshot_id))


def _scope_snapshot_id(
    scope: SectorComponentScope,
    latest: SectorComponentBacktestResult | None,
    config: Any,
) -> str:
    as_of_date = latest.as_of_date if latest is not None else date(1970, 1, 1)
    scope_id = "all" if scope.mode == "all" else str(scope.sector_id)
    parameter_version = _config_text(config, "parameter_version", "sector_component_backtest_unknown")
    return f"sector-component-scope:{scope.mode}:{scope_id}:{as_of_date.isoformat()}:{parameter_version}"


def _reason_codes(
    portfolios: Sequence[SectorComponentSectorPortfolio],
    results: Sequence[SectorComponentBacktestResult],
    warnings: Sequence[SectorComponentValidationWarning],
) -> tuple[str, ...]:
    values = {"SECTOR_COMPONENT_SCOPE_COMPLETED"}
    for portfolio in portfolios:
        values.update(portfolio.reason_codes)
    for result in results:
        values.update(result.reason_codes)
    for warning in warnings:
        values.update(warning.reason_codes)
        values.update(warning.warnings)
    if warnings:
        values.add("REVIEW_REQUIRED")
    return tuple(sorted(values))


def _config_text(config: Any, field_name: str, default: str) -> str:
    if isinstance(config, Mapping):
        value = config.get(field_name, default)
    else:
        value = getattr(config, field_name, default)
    return value if isinstance(value, str) and value.strip() else default
