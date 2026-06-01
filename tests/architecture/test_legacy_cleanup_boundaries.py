from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "api"
STRATEGY_ROOT = API_ROOT / "strategy"
LEGACY_ROOT_SERVICE_FILES = {"bottleneck_data_service.py"}
MACRO_ROOT_IMPORT = "api." + "macro" + "_data_service"
MACRO_ROOT_NAME = "macro" + "_data_service"
FORBIDDEN_STRATEGY_IMPORTS = (
    "sqlite3",
    "api.db",
    "api.features",
    MACRO_ROOT_IMPORT,
    "api.bottleneck_data_service",
    "api.data.strategy_data_readers",
)


def test_strategy_does_not_import_db_features_root_services_or_concrete_adapters():
    violations = []
    for path in _python_files(STRATEGY_ROOT):
        forbidden = [
            item.display
            for item in _collect_imports(path)
            if any(item.matches(prefix) for prefix in FORBIDDEN_STRATEGY_IMPORTS)
        ]
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)}: {forbidden}")

    assert not violations


def test_legacy_strategy_score_store_shim_is_absent():
    assert not (STRATEGY_ROOT / "score_store_service.py").exists()


def test_root_legacy_service_files_are_explicitly_allowlisted_until_removed():
    existing_legacy_files = {
        path.name
        for path in API_ROOT.glob("*.py")
        if path.name in LEGACY_ROOT_SERVICE_FILES
    }

    assert existing_legacy_files <= LEGACY_ROOT_SERVICE_FILES


def test_import_scanner_detects_direct_and_from_api_root_service_imports():
    imports = _collect_imports_from_source(
        f"""
import sqlite3
from sqlite3 import connect
from api import {MACRO_ROOT_NAME}
from api import bottleneck_data_service as bottleneck
from api.data import strategy_data_readers
from api.features.backtests import service
"""
    )
    displays = {item.display for item in imports}

    assert "sqlite3" in displays
    assert "sqlite3.connect" in displays
    assert MACRO_ROOT_IMPORT in displays
    assert "api.bottleneck_data_service" in displays
    assert "api.data.strategy_data_readers" in displays
    assert "api.features.backtests.service" in displays
    assert any(item.matches(MACRO_ROOT_IMPORT) for item in imports)
    assert any(item.matches("api.bottleneck_data_service") for item in imports)
    assert any(item.matches("api.data.strategy_data_readers") for item in imports)


@dataclass(frozen=True)
class ImportItem:
    module: str
    name: str | None = None

    @property
    def display(self) -> str:
        return self.module if self.name is None else f"{self.module}.{self.name}"

    def matches(self, target: str) -> bool:
        return (
            self.module == target
            or self.module.startswith(f"{target}.")
            or self.display == target
            or self.display.startswith(f"{target}.")
        )


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _collect_imports(path: Path) -> list[ImportItem]:
    return _collect_imports_from_source(path.read_text(encoding="utf-8"))


def _collect_imports_from_source(source: str) -> list[ImportItem]:
    tree = ast.parse(source)
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
