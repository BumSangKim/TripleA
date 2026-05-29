import sqlite3

import pytest

from api.db.migrations.runner import run_migrations


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_first_run_applies_migration():
    conn = make_conn()
    applied = []

    def migration_a(c):
        applied.append("a")
        c.execute("CREATE TABLE test_a (id INTEGER PRIMARY KEY)")
        c.commit()

    run_migrations(conn, [("0001", migration_a)])
    assert "a" in applied
    row = conn.execute("SELECT 1 FROM schema_migrations WHERE version='0001'").fetchone()
    assert row is not None


def test_second_run_skips_applied():
    conn = make_conn()
    call_count = [0]

    def migration_a(c):
        call_count[0] += 1
        c.execute("CREATE TABLE IF NOT EXISTS test_b (id INTEGER PRIMARY KEY)")
        c.commit()

    run_migrations(conn, [("0001", migration_a)])
    run_migrations(conn, [("0001", migration_a)])
    assert call_count[0] == 1


def test_failure_not_recorded():
    conn = make_conn()

    def bad_migration(c):
        raise RuntimeError("intentional failure")

    with pytest.raises(RuntimeError):
        run_migrations(conn, [("0001_bad", bad_migration)])

    row = conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version='0001_bad'"
    ).fetchone()
    assert row is None


def test_multiple_migrations_applied_in_order():
    conn = make_conn()
    order = []

    def mig1(c):
        order.append(1)
        c.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
        c.commit()

    def mig2(c):
        order.append(2)
        c.execute("CREATE TABLE t2 (id INTEGER PRIMARY KEY)")
        c.commit()

    run_migrations(conn, [("0001", mig1), ("0002", mig2)])
    assert order == [1, 2]
