from __future__ import annotations

import ast
from dataclasses import asdict
from datetime import date
from pathlib import Path

from api.domain.strategy_inputs import MacroIndicatorInput, MacroSnapshotInput
from api.score_pipeline.adapters.macro_distribution_adapter import MacroDistributionAdapter


def test_macro_snapshot_fixture_adapts_to_score_pipeline_distribution():
    snapshot = MacroSnapshotInput(
        as_of_date=date(2024, 3, 10),
        indicators={
            "VIXCLS": MacroIndicatorInput("VIXCLS", 40.0, "pt", date(2024, 3, 8), "fixture"),
            "ISM_PMI": MacroIndicatorInput("ISM_PMI", 44.0, "pt", date(2024, 3, 8), "fixture"),
        },
    )

    output = MacroDistributionAdapter().adapt(snapshot)

    assert round(sum(output.distribution.values()), 6) == 1.0
    assert output.dominant_regime == "volatility_stress"
    assert output.dominant_regime_explanation_only is True
    assert output.parameter_version == "legacy_macro_distribution_adapter_v1"


def test_missing_indicator_uses_neutral_review_required_fallback():
    output = MacroDistributionAdapter().adapt(MacroSnapshotInput(as_of_date=date(2024, 3, 10)))

    assert output.distribution == {
        "risk_on_growth": 0.0,
        "neutral": 1.0,
        "inflation_pressure": 0.0,
        "recession_risk": 0.0,
        "volatility_stress": 0.0,
    }
    assert output.confidence == 0.0
    assert output.data_quality == 0.0
    assert output.warnings[0].code == "MISSING_MACRO_INPUT_REVIEW_REQUIRED"


def test_previous_score_change_evidence_is_deterministic():
    snapshot = MacroSnapshotInput(
        as_of_date=date(2024, 3, 10),
        indicators={
            "VIXCLS": MacroIndicatorInput("VIXCLS", 18.0, "pt", date(2024, 3, 8), "fixture"),
        },
    )

    output = MacroDistributionAdapter().adapt(snapshot, previous_score=40)

    details = [reason.detail for reason in output.reason_codes if reason.code == "MACRO_SCORE_CHANGE_EVIDENCE"]
    assert details == ["previous_score=40;current_score=50;change=0.1000"]


def test_adapter_output_contains_no_execution_or_broker_fields():
    output = MacroDistributionAdapter().adapt(MacroSnapshotInput(as_of_date=date(2024, 3, 10)))
    keys = set(asdict(output))

    assert {"order", "orders", "execution", "broker"}.isdisjoint(keys)


def test_macro_distribution_adapter_imports_no_db_fastapi_or_features():
    path = Path("api/score_pipeline/adapters/macro_distribution_adapter.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"fastapi", "starlette", "sqlite3", "api.db", "api.features"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)
