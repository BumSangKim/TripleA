from __future__ import annotations

import ast
from pathlib import Path


def test_semiconductor_ai_capex_adapter_has_no_reverse_strategy_or_allocation_dependency() -> None:
    source = (Path(__file__).resolve().parents[2] / "api" / "score_pipeline" / "semiconductor_ai_capex_adapter.py").read_text()
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    forbidden = ("api.strategy", "api.features", "api.brokers", "api.db")
    assert not any(module == term or module.startswith(f"{term}.") for module in imports for term in forbidden)
