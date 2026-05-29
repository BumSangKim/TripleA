import importlib
import sqlite3

from api.db.migrations.runner import run_migrations
from api.db.seeds.runner import run_seeds

_m = importlib.import_module("api.db.migrations.0001_baseline_existing_schema")
_apply_baseline = _m.apply
_BASELINE_VERSION = _m.VERSION


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def setup_db() -> sqlite3.Connection:
    conn = make_conn()
    run_migrations(conn, [(_BASELINE_VERSION, _apply_baseline)])
    return conn


def test_seed_runner_runs_without_error_on_baseline_db():
    conn = setup_db()
    run_seeds(conn)  # should not raise


def test_seed_runner_calls_registered_seeds(monkeypatch):
    import api.db.seeds.runner as runner_module

    called = []

    def fake_seed(c):
        called.append("fake")

    monkeypatch.setattr(runner_module, "_SEEDS", [fake_seed])
    conn = make_conn()
    run_seeds(conn)
    assert called == ["fake"]


def test_seed_runner_calls_in_order(monkeypatch):
    import api.db.seeds.runner as runner_module

    order = []

    monkeypatch.setattr(runner_module, "_SEEDS", [
        lambda c: order.append(1),
        lambda c: order.append(2),
        lambda c: order.append(3),
    ])
    run_seeds(make_conn())
    assert order == [1, 2, 3]
