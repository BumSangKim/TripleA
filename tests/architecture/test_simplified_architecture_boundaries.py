from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVE_SOURCE_ROOTS = (ROOT / "api", ROOT / "config", ROOT / "scripts")
FORBIDDEN_IMPORT_PREFIXES = (
    "api.brokers",
    "api.providers",
    "api.features.orders",
    "api.data.adapters.kis_readonly",
    "api.market_data.price_provider",
    "api.telegram_service",
    "api.macro_telegram_report",
)
FORBIDDEN_EXECUTION_SYMBOLS = (
    "place_order",
    "submit_order",
    "send_order",
    "execute_order",
    "execute_draft",
    "LiveTradingProvider",
    "PaperTradingProvider",
    "TELEGRAM_BOT_TOKEN",
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
)


def test_active_source_does_not_import_removed_live_modules():
    violations: list[str] = []
    for path in _python_files(ACTIVE_SOURCE_ROOTS):
        imports = _collect_imports(path)
        forbidden = [
            module
            for module in imports
            if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
        ]
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)}: {forbidden}")

    assert not violations


def test_active_source_does_not_reference_live_order_or_reporting_symbols():
    violations: list[str] = []
    for path in _python_files(ACTIVE_SOURCE_ROOTS):
        text = path.read_text(encoding="utf-8")
        found = [symbol for symbol in FORBIDDEN_EXECUTION_SYMBOLS if symbol in text]
        if found:
            violations.append(f"{path.relative_to(ROOT)}: {found}")

    assert not violations


def test_supported_tests_do_not_import_removed_live_modules():
    violations: list[str] = []
    for path in _python_files((ROOT / "tests",)):
        imports = _collect_imports(path)
        forbidden = [
            module
            for module in imports
            if any(module == prefix or module.startswith(f"{prefix}.") for prefix in FORBIDDEN_IMPORT_PREFIXES)
        ]
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)}: {forbidden}")

    assert not violations


def test_app_imports_without_live_credential_environment(monkeypatch):
    for key in ("KIS_APP_KEY", "KIS_APP_SECRET", "APP_KEY", "APP_SECRET", "ACCESS_TOKEN", "TELEGRAM_BOT_TOKEN"):
        monkeypatch.delenv(key, raising=False)

    from api.main import app

    assert app.title == "TripleA Dashboard API"


def test_canonical_root_guides_define_removed_live_boundaries():
    master = (ROOT / "MASTER_DEVELOPMENT_GUIDE.md").read_text(encoding="utf-8")
    status = (ROOT / "DevelopPlans" / "STATUS.md").read_text(encoding="utf-8")

    docs_root = ROOT / "docs"
    if docs_root.exists():
        unexpected_docs = [
            path.relative_to(ROOT)
            for path in docs_root.rglob("*")
            if path.is_file() and not _is_allowed_scoring_doc(path)
        ]
        assert not unexpected_docs
    assert "Do not depend on `docs/` as the source of truth" in master
    for phrase in (
        "broker, KIS, live execution, or account mutation",
        "No default automatic execution",
    ):
        assert phrase in master
    for phrase in (
        "`docs/` has been intentionally removed",
        "live broker order submission, real-account mutation, automatic execution",
    ):
        assert phrase in status


def _python_files(roots: tuple[Path, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts and ".pytest_cache" not in path.parts
        )
    return sorted(files)


def _collect_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _is_allowed_scoring_doc(path: Path) -> bool:
    if path.name.startswith("AI_CAPEX_TOKEN_"):
        return True
    return path.is_relative_to(ROOT / "docs" / "ai_capex_token")
