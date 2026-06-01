from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_decision_feedback_domain_contracts_are_pure():
    for relative in ("api/domain/decision_feedback.py", "api/domain/decision_state.py"):
        imports = _collect_imports(ROOT / relative)
        forbidden = _matching_imports(imports, ("fastapi", "starlette", "sqlite3", "api.db", "api.features"))

        assert not forbidden, f"{relative}: {forbidden}"


def test_decision_orchestrator_has_no_transport_db_or_execution_coupling():
    path = ROOT / "api/score_pipeline/orchestrator.py"
    imports = _collect_imports(path)
    forbidden_imports = _matching_imports(
        imports,
        ("fastapi", "starlette", "sqlite3", "api.db", "api.features", "api.brokers", "api.providers"),
    )
    text = path.read_text(encoding="utf-8").lower()
    forbidden_tokens = [token for token in ("submit", "execute_order", "broker", "kis_order") if token in text]

    assert not forbidden_imports
    assert not forbidden_tokens


def test_macro_distribution_adapter_only_reuses_legacy_macro_formula():
    path = ROOT / "api/score_pipeline/adapters/macro_distribution_adapter.py"
    imports = _collect_imports(path)
    forbidden = _matching_imports(
        imports,
        ("fastapi", "starlette", "sqlite3", "api.db", "api.features", "api.providers", "api.brokers"),
    )
    strategy_imports = [item for item in imports if item.module.startswith("api.strategy")]

    assert not forbidden
    assert all(item.module == "api.strategy.macro_engine" for item in strategy_imports)
    imported_names = {item.name for item in strategy_imports}
    assert "TripleAAllocator" not in imported_names
    assert "evaluate_macro_snapshot" in imported_names


def test_docs_tree_only_contains_explicit_scoring_specs_when_present():
    docs_root = ROOT / "docs"
    if not docs_root.exists():
        return

    unexpected = [
        path.relative_to(ROOT)
        for path in docs_root.rglob("*")
        if path.is_file() and not path.name.startswith("AI_CAPEX_TOKEN_")
    ]

    assert not unexpected


def test_lower_layer_contracts_do_not_call_upper_concrete_engines():
    for relative in ("api/domain/decision_feedback.py", "api/domain/decision_state.py"):
        imports = _collect_imports(ROOT / relative)
        forbidden = _matching_imports(
            imports,
            (
                "api.strategy.triplea_allocator",
                "api.strategy.risk_budget_engine",
                "api.strategy.sector_tilt_engine",
                "api.strategy.order_candidates",
                "api.features.rebalancing",
            ),
        )

        assert not forbidden, f"{relative}: {forbidden}"


def test_orchestrator_does_not_import_concrete_allocator():
    imports = _collect_imports(ROOT / "api/score_pipeline/orchestrator.py")
    forbidden = [
        item.display
        for item in imports
        if item.module == "api.strategy.triplea_allocator" or item.name == "TripleAAllocator"
    ]

    assert not forbidden


class ImportItem:
    def __init__(self, module: str, name: str | None = None) -> None:
        self.module = module
        self.name = name

    @property
    def display(self) -> str:
        return f"{self.module}.{self.name}" if self.name else self.module


def _collect_imports(path: Path) -> list[ImportItem]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[ImportItem] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(ImportItem(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.names:
                imports.extend(ImportItem(node.module, alias.name) for alias in node.names)
            else:
                imports.append(ImportItem(node.module))
    return imports


def _matching_imports(imports: list[ImportItem], prefixes: tuple[str, ...]) -> list[str]:
    return [
        item.display
        for item in imports
        if any(item.module == prefix or item.module.startswith(f"{prefix}.") for prefix in prefixes)
    ]
