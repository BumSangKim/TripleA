from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKTESTS_REPOSITORY = ROOT / "api" / "features" / "backtests" / "repository.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "api.strategy",
    "api.market_data_collector",
    "api.market_data_service",
    "api.data.strategy_data_readers",
    "api.features.market_data.trade_data_service",
)


def test_backtests_repository_does_not_import_strategy_or_market_data_orchestration():
    imports = _collect_imports(BACKTESTS_REPOSITORY)
    violations = [
        item.display
        for item in imports
        if any(item.matches(prefix) for prefix in FORBIDDEN_IMPORT_PREFIXES)
    ]

    assert not violations, (
        f"{BACKTESTS_REPOSITORY.relative_to(ROOT)} imports orchestration dependencies: "
        + ", ".join(violations)
    )


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
