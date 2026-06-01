from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_removed_live_test_artifacts_are_absent():
    removed_paths = [
        ROOT / "tests" / "brokers",
        ROOT / "tests" / "providers",
        ROOT / "tests" / "features" / "orders",
        ROOT / "tests" / "fixtures" / "data" / "kis_readonly",
        ROOT / "tests" / "integration" / "test_live_price_query_smoke.py",
        ROOT / "tests" / "integration" / "test_universe_live_data_db_e2e.py",
        ROOT / "tests" / "test_api_orders.py",
        ROOT / "tests" / "test_kis_provider.py",
        ROOT / "tests" / "test_macro_telegram_report.py",
        ROOT / "tests" / "test_price_provider_contract.py",
    ]

    assert not [path for path in removed_paths if path.exists()]


def test_supported_pytest_markers_do_not_include_live_price():
    pytest_ini = (ROOT / "pytest.ini").read_text(encoding="utf-8")

    assert "live_price" not in pytest_ini


def test_app_import_does_not_require_live_credentials(monkeypatch):
    for key in (
        "KIS_APP_KEY",
        "KIS_APP_SECRET",
        "KIS_ACCOUNT_NO",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "APP_KEY",
        "APP_SECRET",
        "ACCESS_TOKEN",
        "API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    from api.main import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert app.title
    assert not any(path.startswith("/api/orders") for path in paths)
    assert not any("sync-accounts" in path for path in paths)


def test_supported_suite_does_not_require_local_secret_files():
    committed_secret_names = {
        ".env",
        "API_KEY",
        "economic_data.db",
    }
    tracked_test_paths = [
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "tests").rglob("*")
        if path.is_file() and path.name in committed_secret_names
    ]

    assert not tracked_test_paths
