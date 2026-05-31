from __future__ import annotations

from fastapi import FastAPI


def include_feature_routers(app: FastAPI) -> None:
    from api.features.alerts.router import router as alerts_router
    from api.features.calendar.router import router as calendar_router
    from api.features.capex_cycle.router import router as capex_cycle_router
    from api.features.documents.router import router as documents_router
    from api.features.search.router import router as search_router
    from api.features.data_status.router import router as data_status_router
    from api.features.market_data.router import router as market_data_router
    from api.features.dashboard.router import router as dashboard_router
    from api.features.accounts.router import router as accounts_router
    from api.features.auth.router import router as auth_router
    from api.features.backtests.router import router as backtests_router
    from api.features.holdings.router import router as holdings_router
    from api.features.intraday.router import router as intraday_router
    from api.features.macro.router import router as macro_router
    from api.features.orders.router import router as orders_router
    from api.features.rebalancing.router import router as rebalancing_router
    from api.features.strategy.router import router as strategy_router
    from api.features.system.router import router as system_router
    from api.features.targets.router import router as targets_router

    app.include_router(alerts_router)
    app.include_router(calendar_router)
    app.include_router(capex_cycle_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(data_status_router)
    app.include_router(market_data_router)
    app.include_router(dashboard_router)
    app.include_router(accounts_router)
    app.include_router(auth_router)
    app.include_router(backtests_router)
    app.include_router(holdings_router)
    app.include_router(intraday_router)
    app.include_router(macro_router)
    app.include_router(orders_router)
    app.include_router(rebalancing_router)
    app.include_router(strategy_router)
    app.include_router(system_router)
    app.include_router(targets_router)
