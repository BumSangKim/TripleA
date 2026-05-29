from __future__ import annotations

import sqlite3

from api.db.seeds.default_targets import seed as seed_targets
from api.db.seeds.account_policies import seed as seed_account_policies
from api.db.seeds.engine_allocations import seed as seed_engine_allocations
from api.db.seeds.asset_universe import seed as seed_asset_universe
from api.db.seeds.investment_universe import seed as seed_investment_universe
from api.db.seeds.sector_maps import seed as seed_sector_maps

_SEEDS = [
    seed_targets,
    seed_account_policies,
    seed_engine_allocations,
    seed_asset_universe,
    seed_investment_universe,
    seed_sector_maps,
]


def run_seeds(conn: sqlite3.Connection) -> None:
    """Run all registered seed functions in order."""
    for seed_fn in _SEEDS:
        seed_fn(conn)
    conn.commit()
