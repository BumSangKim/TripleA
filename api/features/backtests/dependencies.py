from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.backtests.repository import BacktestsRepository
from api.features.backtests.service import BacktestsService
from api.features.backtests.sector_component_data_provider import FileSectorComponentBacktestDataProvider
from api.features.backtests.sector_component_config import (
    SectorComponentBacktestConfig,
    load_sector_component_backtest_config,
)
from api.features.backtests.sector_component_portfolios import (
    SectorComponentSectorPortfolio,
    load_sector_component_sector_portfolios,
)
from api.features.backtests.sector_component_runner import run_sector_component_backtest
from api.features.backtests.sector_component_scope_runner import run_sector_component_scope_backtest


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_backtests_repository(
    conn: sqlite3.Connection = Depends(get_db),
) -> BacktestsRepository:
    return BacktestsRepository(conn)


def get_backtests_service(
    repo: BacktestsRepository = Depends(get_backtests_repository),
) -> BacktestsService:
    return BacktestsService(
        repo,
        sector_component_data_provider=FileSectorComponentBacktestDataProvider(),
        sector_component_runner=run_sector_component_backtest,
        sector_component_scope_runner=run_sector_component_scope_backtest,
    )


def get_sector_component_config() -> SectorComponentBacktestConfig:
    return load_sector_component_backtest_config()


def get_sector_component_portfolios() -> tuple[SectorComponentSectorPortfolio, ...]:
    return load_sector_component_sector_portfolios()
