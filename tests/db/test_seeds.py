import importlib
import sqlite3

import pytest

from api.db.migrations.runner import run_migrations
from api.db.seeds.runner import run_seeds

_m = importlib.import_module("api.db.migrations.0001_baseline_existing_schema")
apply_baseline = _m.apply
BASELINE_VERSION = _m.VERSION


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def setup_db() -> sqlite3.Connection:
    conn = make_conn()
    run_migrations(conn, [(BASELINE_VERSION, apply_baseline)])
    return conn


def test_run_seeds_no_error():
    conn = setup_db()
    run_seeds(conn)  # should not raise


def test_run_seeds_idempotent():
    conn = setup_db()
    run_seeds(conn)
    run_seeds(conn)  # second run should not raise


def test_default_targets_seeded():
    conn = setup_db()
    run_seeds(conn)
    row = conn.execute("SELECT COUNT(*) FROM targets").fetchone()
    assert row[0] > 0


def test_account_policies_seeded():
    conn = setup_db()
    run_seeds(conn)
    row = conn.execute("SELECT COUNT(*) FROM account_policies").fetchone()
    assert row[0] > 0


def test_engine_allocations_seeded():
    conn = setup_db()
    run_seeds(conn)
    row = conn.execute("SELECT COUNT(*) FROM engine_allocations").fetchone()
    assert row[0] > 0
