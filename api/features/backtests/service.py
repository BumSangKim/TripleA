from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any

from api.backtest_engine import BacktestConfig
from api.features.backtests.ports import (
    IBacktestExecutionRunner,
    IBacktestsRepository,
    ISectorComponentBacktestDataProvider,
    ISectorComponentBacktestRunner,
    ISectorComponentScopeBacktestRunner,
)
from api.features.backtests.sector_component_models import (
    CONSERVATIVE_FALLBACK_STATES,
    SectorComponentBacktestResult,
    SectorComponentValidationWarning,
)
from api.features.backtests.sector_component_scope import (
    SectorComponentScope,
    SectorComponentScopedBacktestResult,
)


class BacktestsService:
    def __init__(
        self,
        repo: IBacktestsRepository,
        *,
        backtest_execution_runner: IBacktestExecutionRunner | None = None,
        sector_component_data_provider: ISectorComponentBacktestDataProvider | None = None,
        sector_component_runner: ISectorComponentBacktestRunner | None = None,
        sector_component_scope_runner: ISectorComponentScopeBacktestRunner | None = None,
    ) -> None:
        self._repo = repo
        self._backtest_execution_runner = backtest_execution_runner
        self._sector_component_data_provider = sector_component_data_provider
        self._sector_component_runner = sector_component_runner
        self._sector_component_scope_runner = sector_component_scope_runner

    def run_backtest(self, body: Any) -> Any:
        save_result = getattr(self._repo, "save_backtest_result", None)
        if self._backtest_execution_runner is not None and callable(save_result):
            config = _backtest_config_from_request(body)
            result = self._backtest_execution_runner.run(config)
            return save_result(body, config, result)
        return self._repo.run_backtest(body)

    def run_sector_component_backtest(self, config: Any) -> Any:
        if self._sector_component_data_provider is None or self._sector_component_runner is None:
            return self._sector_component_fallback(
                config,
                "SECTOR_COMPONENT_SERVICE_NOT_CONFIGURED",
                "sector component data provider or runner is not configured",
            )

        observations = tuple(self._sector_component_data_provider.list_sector_component_observations(config))
        historical_returns = tuple(self._sector_component_data_provider.list_sector_component_returns(config))
        macro_regime_records = tuple(self._sector_component_data_provider.list_sector_component_regimes(config))
        if not observations:
            return self._sector_component_fallback(
                config,
                "SECTOR_COMPONENT_OBSERVATIONS_MISSING",
                "sector component observations are missing",
            )
        if not historical_returns:
            return self._sector_component_fallback(
                config,
                "SECTOR_COMPONENT_HISTORICAL_DATA_MISSING",
                "sector component historical returns are missing",
            )
        return self._sector_component_runner(
            config,
            observations,
            historical_returns,
            macro_regime_records=macro_regime_records,
        )

    def run_sector_component_scope_backtest(
        self,
        scope: SectorComponentScope,
        config: Any,
        portfolios: list[Any] | tuple[Any, ...],
    ) -> Any:
        if self._sector_component_data_provider is None:
            return self._sector_component_scope_fallback(
                scope,
                config,
                "SECTOR_COMPONENT_DATA_PROVIDER_NOT_CONFIGURED",
                "sector component data provider is not configured",
            )
        if self._sector_component_scope_runner is None:
            return self._sector_component_scope_fallback(
                scope,
                config,
                "SECTOR_COMPONENT_SCOPE_RUNNER_NOT_CONFIGURED",
                "sector component scope runner is not configured",
            )

        observations = tuple(self._sector_component_data_provider.list_sector_component_observations(config))
        historical_returns = tuple(self._sector_component_data_provider.list_sector_component_returns(config))
        macro_regime_records = tuple(self._sector_component_data_provider.list_sector_component_regimes(config))
        if not observations:
            return self._sector_component_scope_fallback(
                scope,
                config,
                "SECTOR_COMPONENT_OBSERVATIONS_MISSING",
                "sector component observations are missing",
            )
        return self._sector_component_scope_runner(
            config,
            observations,
            historical_returns,
            macro_regime_records,
            tuple(portfolios),
            scope,
        )

    def list_runs(self, limit: int) -> list[Any]:
        return self._repo.list_runs(limit)

    def get_run(self, run_id: int) -> Any:
        return self._repo.get_run(run_id)

    def get_decisions(self, run_id: int) -> list[Any]:
        return self._repo.get_decisions(run_id)

    def get_positions(self, run_id: int) -> list[Any]:
        return self._repo.get_positions(run_id)

    def get_trades(self, run_id: int) -> list[Any]:
        return self._repo.get_trades(run_id)

    def _sector_component_fallback(self, config: Any, code: str, message: str) -> SectorComponentBacktestResult:
        as_of_date = date(1970, 1, 1)
        available_at = datetime.combine(as_of_date, time.min, tzinfo=UTC)
        fallback_policy = _fallback_policy(config)
        parameter_version = _config_text(config, "parameter_version", "sector_component_backtest_unknown")
        model_version = _config_text(config, "model_version", "sector_component_backtest_service")
        warning = SectorComponentValidationWarning(
            sector_id="UNKNOWN",
            as_of_date=as_of_date,
            available_at=available_at,
            parameter_version=parameter_version,
            model_version=model_version,
            data_snapshot_id="sector-component-service:missing-input",
            reason_codes=("REVIEW_REQUIRED",),
            warnings=(code,),
            code=code,
            message=message,
            fallback_state=fallback_policy,
        )
        return SectorComponentBacktestResult(
            sector_id="UNKNOWN",
            as_of_date=as_of_date,
            available_at=available_at,
            parameter_version=parameter_version,
            model_version=model_version,
            data_snapshot_id="sector-component-service:missing-input",
            status=fallback_policy,
            reason_codes=("REVIEW_REQUIRED", code),
            warnings=(warning,),
        )

    def _sector_component_scope_fallback(
        self,
        scope: SectorComponentScope,
        config: Any,
        code: str,
        message: str,
    ) -> SectorComponentScopedBacktestResult:
        as_of_date = date(1970, 1, 1)
        available_at = datetime.combine(as_of_date, time.min, tzinfo=UTC)
        fallback_policy = _fallback_policy(config)
        parameter_version = _config_text(config, "parameter_version", "sector_component_backtest_unknown")
        model_version = _config_text(config, "model_version", "sector_component_scope_service")
        warning = SectorComponentValidationWarning(
            sector_id=scope.sector_id or "ALL",
            as_of_date=as_of_date,
            available_at=available_at,
            parameter_version=parameter_version,
            model_version=model_version,
            data_snapshot_id="sector-component-scope-service:missing-input",
            reason_codes=("REVIEW_REQUIRED",),
            warnings=(code,),
            code=code,
            message=message,
            fallback_state=fallback_policy,
        )
        return SectorComponentScopedBacktestResult(
            sector_scope=scope,
            parameter_version=parameter_version,
            model_version=model_version,
            data_snapshot_id="sector-component-scope-service:missing-input",
            status=fallback_policy,
            reason_codes=("REVIEW_REQUIRED", code),
            warnings=(warning,),
        )


def _config_text(config: Any, field_name: str, default: str) -> str:
    if isinstance(config, dict):
        value = config.get(field_name, default)
    else:
        value = getattr(config, field_name, default)
    return value if isinstance(value, str) and value.strip() else default


def _fallback_policy(config: Any) -> str:
    value = _config_text(config, "fallback_policy", "REVIEW_REQUIRED")
    return value if value in CONSERVATIVE_FALLBACK_STATES else "REVIEW_REQUIRED"


def _backtest_config_from_request(body: Any) -> BacktestConfig:
    return BacktestConfig(
        start_date=_request_date(body, "startDate"),
        end_date=_request_date(body, "endDate"),
        initial_capital=float(_request_value(body, "initialCapital", 0)),
        rebalance_frequency=_request_text(body, "rebalanceFrequency", "monthly").lower(),
        strategy_mode=_request_text(body, "strategyMode", "triplea_dynamic").lower(),
        risk_profile=_request_text(body, "riskProfile", "balanced").lower(),
        universe_id=_request_text(body, "universeId", "default_global").lower(),
        base_currency=_request_text(body, "baseCurrency", "KRW").upper(),
        fee_bps=float(_request_value(body, "feeBps", 0.0)),
        slippage_bps=float(_request_value(body, "slippageBps", 0.0)),
        tax_bps=float(_request_value(body, "taxBps", 0.0)),
        data_lookback_years=int(_request_value(body, "dataLookbackYears", 5)),
    )


def _request_date(body: Any, field_name: str) -> date:
    value = _request_value(body, field_name, None)
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be YYYY-MM-DD") from exc


def _request_text(body: Any, field_name: str, default: str) -> str:
    value = _request_value(body, field_name, default)
    text = str(value or default).strip()
    return text or default


def _request_value(body: Any, field_name: str, default: Any) -> Any:
    if isinstance(body, dict):
        return body.get(field_name, default)
    return getattr(body, field_name, default)
