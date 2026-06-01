from __future__ import annotations

import ast
from pathlib import Path

from api.main import app


ROOT = Path(__file__).resolve().parents[2]


def test_active_api_has_no_order_provider_broker_or_execution_routes():
    forbidden_terms = ("order", "orders", "provider", "broker", "execute", "execution", "sync-accounts")
    violations = []

    for route in app.routes:
        path = getattr(route, "path", "").lower()
        if any(term in path for term in forbidden_terms):
            violations.append(path)

    assert not violations


def test_active_feature_registry_does_not_import_deleted_order_or_provider_features():
    imports = _collect_imports(ROOT / "api" / "features" / "router_registry.py")

    assert "api.features.orders.router" not in imports
    assert not any(module.startswith("api.providers") for module in imports)
    assert not any(module.startswith("api.brokers") for module in imports)


def test_simplified_public_outputs_are_not_executable_order_contracts():
    from api.features.rebalancing.schemas import RebalanceResultItem, RebalanceRunResponse
    from api.features.backtests.schemas import BacktestRunResponse

    for model in (RebalanceResultItem, RebalanceRunResponse, BacktestRunResponse):
        field_names = set(model.model_fields)
        assert "executionAllowed" not in field_names
        assert "orderDraftId" not in field_names
        assert "brokerOrderPayload" not in field_names


def _collect_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports
