from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ROUTER = ROOT / "api" / "features" / "intraday" / "router.py"
INIT = ROOT / "api" / "features" / "intraday" / "__init__.py"


def test_intraday_router_uses_service_dependency_not_db_repository_or_collector():
    imports = _collect_imports(ROUTER)
    forbidden = [
        item.display
        for item in imports
        if item.matches("api.db")
        or item.matches("api.features.intraday.repository")
        or item.matches("api.features.intraday.collector")
        or item.display == "api.features.intraday.get_conn"
        or item.display.endswith(".get_conn")
    ]

    assert not forbidden


def test_intraday_package_does_not_reexport_get_conn():
    imports = _collect_imports(INIT)
    imported_names = {item.display for item in imports}

    assert "api.db.connection.get_conn" not in imported_names


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


def _collect_imports(path: Path) -> list[ImportItem]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[ImportItem] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(ImportItem(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append(ImportItem(module))
            imports.extend(ImportItem(module, alias.name) for alias in node.names)
    return imports
