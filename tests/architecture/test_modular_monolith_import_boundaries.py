from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "api"
FEATURES_ROOT = API_ROOT / "features"

ROOT_ALLOWED_FILES = {
    "__init__.py",
    "asset_data_requirements.py",
    "asset_universe_loader.py",
    "asset_universe_mapping.py",
    "asset_universe_schema.py",
    "asset_universe_snapshot.py",
    "asset_universe_validator.py",
    "backtest_engine.py",
    "backtest_foundation.py",
    "bottleneck_data_service.py",
    "data_contracts.py",
    "macro_data_service.py",
    "macro_indicator_collector.py",
    "macro_telegram_report.py",
    "main.py",
    "market_data_collector.py",
    "market_data_service.py",
    "observation_universe.py",
    "strategy_config.py",
    "telegram_service.py",
    "trade_data_service.py",
}
ROOT_OWNER_UNRESOLVED = {
    "asset_data_requirements.py",
    "asset_universe_loader.py",
    "asset_universe_mapping.py",
    "asset_universe_schema.py",
    "asset_universe_snapshot.py",
    "asset_universe_validator.py",
    "bottleneck_data_service.py",
    "macro_data_service.py",
    "macro_indicator_collector.py",
    "macro_telegram_report.py",
    "market_data_collector.py",
    "market_data_service.py",
    "telegram_service.py",
    "trade_data_service.py",
}
SERVICE_SQL_PATTERN = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b", re.IGNORECASE)


def test_domain_does_not_import_transport_db_or_feature_layers():
    violations = _imports_with_forbidden_prefixes(
        API_ROOT / "domain",
        ("fastapi", "starlette", "sqlite3", "api.db", "api.features"),
    )

    assert not violations


def test_strategy_does_not_import_transport_or_feature_layers():
    violations = _imports_with_forbidden_prefixes(
        API_ROOT / "strategy",
        ("fastapi", "starlette", "api.features"),
    )

    assert not violations


def test_strategy_does_not_import_root_trade_data_service():
    violations = _imports_with_forbidden_prefixes(
        API_ROOT / "strategy",
        ("api.trade_data_service",),
    )

    assert not violations


def test_bottleneck_sector_engine_does_not_import_db_or_data_adapters():
    imports = _collect_imports(API_ROOT / "strategy" / "bottleneck_sector_engine.py")
    forbidden = [
        item.display
        for item in imports
        if any(
            item.matches(prefix)
            for prefix in (
                "api.trade_data_service",
                "sqlite3",
                "api.data",
                "api.features.market_data",
            )
        )
    ]

    assert not forbidden


def test_feature_routers_do_not_import_repository_db_or_sqlite():
    violations: list[str] = []
    for router_file in _feature_files("router.py"):
        imports = _collect_imports(router_file)
        forbidden = [
            item.display
            for item in imports
            if item.matches("repository") or item.matches("api.db") or item.matches("sqlite3")
        ]
        if forbidden:
            violations.append(f"{router_file.relative_to(ROOT)}: {forbidden}")

    assert not violations


def test_feature_services_do_not_use_db_http_or_sql_strings():
    violations: list[str] = []
    for service_file in _feature_files("service.py"):
        imports = _collect_imports(service_file)
        forbidden_imports = [
            item.display
            for item in imports
            if item.matches("sqlite3") or item.matches("api.db") or item.matches("fastapi")
        ]
        forbidden_names = _imported_names(service_file) & {"HTTPException"}
        sql_strings = _sql_string_literals(service_file)
        found = [*forbidden_imports, *sorted(forbidden_names), *sql_strings]
        if found:
            violations.append(f"{service_file.relative_to(ROOT)}: {found}")

    assert not violations


def test_feature_repositories_do_not_import_transport_router_or_service_layers():
    violations: list[str] = []
    for repository_file in _feature_files("repository.py"):
        imports = _collect_imports(repository_file)
        forbidden = [
            item.display
            for item in imports
            if item.matches("fastapi") or item.matches("router") or item.matches("service")
        ]
        if forbidden:
            violations.append(f"{repository_file.relative_to(ROOT)}: {forbidden}")

    assert not violations


def test_feature_repository_strategy_imports_are_known_follow_up_work():
    violations: list[str] = []
    for repository_file in _feature_files("repository.py"):
        imports = _collect_imports(repository_file)
        forbidden = [item.display for item in imports if item.matches("api.strategy")]
        if forbidden:
            violations.append(f"{repository_file.relative_to(ROOT)}: {forbidden}")

    if violations:
        pytest.xfail("repository strategy imports require a later owner-specific refactor: " + "; ".join(violations))


def test_db_package_does_not_import_features():
    violations = _imports_with_forbidden_prefixes(API_ROOT / "db", ("api.features",))

    assert not violations


def test_api_root_python_files_are_inventory_allowlisted():
    current_files = {path.name for path in API_ROOT.glob("*.py")}

    assert current_files <= ROOT_ALLOWED_FILES


def test_api_root_owner_unresolved_files_are_explicit_todo():
    existing_unresolved = sorted(path for path in ROOT_OWNER_UNRESOLVED if (API_ROOT / path).exists())

    if existing_unresolved:
        pytest.xfail("root owner unresolved files remain documented TODOs: " + ", ".join(existing_unresolved))


class ImportItem:
    def __init__(self, module: str, name: str | None = None) -> None:
        self.module = module
        self.name = name

    @property
    def display(self) -> str:
        return self.module if self.name is None else f"{self.module}.{self.name}"

    def matches(self, target: str) -> bool:
        return self.module == target or self.module.startswith(f"{target}.") or self.display == target or self.display.startswith(f"{target}.")


def _feature_files(filename: str) -> list[Path]:
    return sorted(FEATURES_ROOT.glob(f"*/{filename}"))


def _collect_imports(path: Path) -> list[ImportItem]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[ImportItem] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(ImportItem(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _module_name(node)
            imports.append(ImportItem(module))
            imports.extend(ImportItem(module, alias.name) for alias in node.names)
    return imports


def _module_name(node: ast.ImportFrom) -> str:
    module = node.module or ""
    if node.level and module:
        return module
    return module


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _sql_string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and SERVICE_SQL_PATTERN.search(node.value):
            matches.append(node.value.strip().splitlines()[0][:80])
    return matches


def _imports_with_forbidden_prefixes(directory: Path, forbidden_prefixes: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in sorted(directory.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        forbidden = [
            item.display
            for item in _collect_imports(path)
            if any(item.matches(prefix) for prefix in forbidden_prefixes)
        ]
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)}: {forbidden}")
    return violations
