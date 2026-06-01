from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AI_DOMAIN_FILE = ROOT / "api" / "domain" / "scoring" / "ai_capex_token_contracts.py"
AI_STRATEGY_FILES = tuple(sorted((ROOT / "api" / "strategy").glob("ai_capex_token*.py")))
FORBIDDEN_DOMAIN_IMPORT_PREFIXES = (
    "fastapi",
    "sqlite3",
    "api.strategy",
    "api.features",
    "api.providers",
    "api.brokers",
    "api.db",
)
FORBIDDEN_STRATEGY_IMPORT_PREFIXES = (
    "fastapi",
    "starlette",
    "sqlite3",
    "api.features",
    "api.providers",
    "api.brokers",
    "api.db",
    "api.execution",
    "api.domain.execution",
)
FORBIDDEN_ACTION_TERMS = (
    "buy",
    "sell",
    "place_order",
    "submit_order",
    "execute_order",
    "live_execute",
    "auto_execute",
    "order_candidate",
    "target_weight",
    "allocation_target",
)


def test_ai_capex_token_domain_contract_remains_pure():
    imports = _collect_imports(AI_DOMAIN_FILE)

    forbidden = _matching_forbidden_imports(imports, FORBIDDEN_DOMAIN_IMPORT_PREFIXES)

    assert forbidden == []


def test_ai_capex_token_strategy_files_do_not_import_features_providers_brokers_or_db():
    violations: list[str] = []
    for path in AI_STRATEGY_FILES:
        forbidden = _matching_forbidden_imports(_collect_imports(path), FORBIDDEN_STRATEGY_IMPORT_PREFIXES)
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)}: {forbidden}")

    assert violations == []


def test_ai_capex_token_files_do_not_define_direct_order_or_execution_actions():
    violations: list[str] = []
    for path in (AI_DOMAIN_FILE, *AI_STRATEGY_FILES):
        tree = _parse(path)
        function_names = [
            node.name.lower()
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        forbidden_names = [name for name in function_names if any(term in name for term in FORBIDDEN_ACTION_TERMS)]
        if forbidden_names:
            violations.append(f"{path.relative_to(ROOT)}: {forbidden_names}")

    assert violations == []


def test_dominant_scenario_is_not_mapped_to_fixed_weights_or_targets():
    violations: list[str] = []
    risky_assignment_terms = ("weight", "target", "allocation", "rebalance")
    for path in AI_STRATEGY_FILES:
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and _contains_name_or_attr(node.test, "dominant_scenario"):
                assigned_names = [
                    target.id.lower()
                    for nested in ast.walk(node)
                    if isinstance(nested, ast.Assign)
                    for target in nested.targets
                    if isinstance(target, ast.Name)
                ]
                if any(any(term in name for term in risky_assignment_terms) for name in assigned_names):
                    violations.append(f"{path.relative_to(ROOT)}: dominant_scenario controls {assigned_names}")

    assert violations == []


def test_inverse_component_remains_diagnostic_without_order_target_or_allocation_fields():
    path = ROOT / "api" / "strategy" / "ai_capex_token_sector_components.py"
    tree = _parse(path)
    inverse_function = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "score_inverse_hedge_diagnostic"
    ]
    assert len(inverse_function) == 1

    string_literals = [
        node.value.lower()
        for node in ast.walk(inverse_function[0])
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]

    assert "inverse_hedge_diagnostic" in string_literals
    assert "requires_existing_hedge_policy" in string_literals
    assert not any(term in literal for literal in string_literals for term in ("order", "target_weight", "allocation"))


def _collect_imports(path: Path) -> list[str]:
    tree = _parse(path)
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


def _parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _matching_forbidden_imports(imports: list[str], prefixes: tuple[str, ...]) -> list[str]:
    return [
        module
        for module in imports
        if any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)
    ]


def _contains_name_or_attr(node: ast.AST, name: str) -> bool:
    for nested in ast.walk(node):
        if isinstance(nested, ast.Name) and nested.id == name:
            return True
        if isinstance(nested, ast.Attribute) and nested.attr == name:
            return True
    return False
