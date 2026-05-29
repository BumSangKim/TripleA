from __future__ import annotations

import importlib

from api.db.connection import get_conn
from api.db.migrations.compat import migrate_existing_schema
from api.db.migrations.runner import run_migrations
from api.db.seeds.runner import run_seeds

_MIGRATIONS = [
    (
        "0001_baseline_existing_schema",
        importlib.import_module("api.db.migrations.0001_baseline_existing_schema").apply,
    ),
]


def initialize_database() -> None:
    """Run all migrations, schema compat upgrades, then seeds.

    Replaces legacy ensure_dashboard_tables().
    """
    with get_conn() as conn:
        run_migrations(conn, _MIGRATIONS)
        migrate_existing_schema(conn)
        run_seeds(conn)
