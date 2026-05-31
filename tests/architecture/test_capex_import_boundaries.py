from __future__ import annotations

import ast
from pathlib import Path

from api.features.capex_cycle.router import router as capex_cycle_router


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IMPORT_PREFIXES = (
    "api.brokers",
    "api.features.orders",
    "api.strategy",
)
FORBIDDEN_LIVE_SYMBOLS = (
    "api.kis",
    "kis_order",
    "broker_order",
    "submit_order",
    "execute_order",
    "place_order",
    "live_execution",
)


def test_capex_plugin_and_feature_layers_do_not_import_execution_or_strategy_paths():
    violations: list[str] = []
    for path in _capex_source_files():
        imports = _collect_imports(path)
        forbidden = [
            module
            for module in imports
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES) or ".kis" in module.lower() or module.lower().endswith(".kis")
        ]
        if forbidden:
            violations.append(f"{path.relative_to(ROOT)}: {forbidden}")

    assert not violations


def test_capex_source_does_not_reference_live_execution_symbols():
    violations: list[str] = []
    for path in _capex_source_files():
        source = path.read_text(encoding="utf-8").lower()
        found = [symbol for symbol in FORBIDDEN_LIVE_SYMBOLS if symbol in source]
        if found:
            violations.append(f"{path.relative_to(ROOT)}: {found}")

    assert not violations


def test_registered_capex_router_remains_readonly():
    routes = [route for route in capex_cycle_router.routes if route.path.startswith("/api/capex-cycle")]

    assert routes
    assert all(route.methods <= {"GET", "HEAD"} for route in routes)
    assert not any("order" in route.path.lower() or "execution" in route.path.lower() for route in routes)


def _capex_source_files() -> list[Path]:
    files = [
        *(ROOT / "api" / "features" / "capex_cycle").glob("*.py"),
        ROOT / "api" / "data" / "adapters" / "ports.py",
        ROOT / "api" / "data" / "adapters" / "fixtures.py",
        ROOT / "api" / "score_pipeline" / "plugins" / "ai_capex_cycle.py",
        ROOT / "api" / "score_pipeline" / "plugins" / "bio_capex_bottleneck.py",
        ROOT / "api" / "score_pipeline" / "plugins" / "capex_common.py",
        ROOT / "api" / "score_pipeline" / "plugins" / "capex_scenario.py",
        ROOT / "api" / "score_pipeline" / "plugins" / "valuation_engine.py",
    ]
    return sorted(path for path in files if path.exists() and "__pycache__" not in path.parts)


def _collect_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports
