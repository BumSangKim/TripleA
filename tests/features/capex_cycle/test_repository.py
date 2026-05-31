from __future__ import annotations

import inspect
from datetime import date

from api.features.capex_cycle.models import (
    CapexDecisionAuditRow,
    CapexScenarioSnapshot,
    CapexScoreSnapshot,
    CapexValuationSnapshot,
)
from api.features.capex_cycle.ports import ICapexCycleRepository
from api.features.capex_cycle.repository import CapexCycleSnapshotRepository
from api.features.capex_cycle.schemas import ReasonItem, WarningItem


def test_repository_retrieves_latest_score_snapshot_by_date():
    older = _score("score-202605", date(2026, 5, 31), score=0.55)
    newer = _score("score-202606", date(2026, 6, 30), score=0.66)
    repo = CapexCycleSnapshotRepository(score_snapshots=[older, newer])

    assert isinstance(repo, ICapexCycleRepository)
    assert repo.get_latest_score_snapshot(as_of_date=date(2026, 6, 30)).snapshot_id == "score-202606"
    assert repo.get_latest_score_snapshot(as_of_date=date(2026, 6, 15)).snapshot_id == "score-202605"


def test_missing_snapshot_returns_none():
    repo = CapexCycleSnapshotRepository()

    assert repo.get_latest_score_snapshot(as_of_date=date(2026, 5, 31)) is None
    assert repo.get_latest_scenario_snapshot(as_of_date=date(2026, 5, 31)) is None
    assert repo.get_latest_valuation_snapshot(asset_id="missing", as_of_date=date(2026, 5, 31)) is None


def test_repository_preserves_version_and_audit_fields():
    scenario = CapexScenarioSnapshot(
        snapshot_id="scenario-1",
        scenario_id="capex_scenario_distribution",
        scenario_distribution={"ai_buildout_continues": 0.5},
        dominant_scenario="ai_buildout_continues",
        confidence=0.8,
        data_quality=0.75,
        as_of_date=date(2026, 5, 31),
        parameter_version="scenario_params_v1",
        model_version="scenario_model_v1",
        reason_codes=[_reason()],
        warnings=[_warning()],
    )
    valuation = CapexValuationSnapshot(
        snapshot_id="valuation-1",
        asset_id="sample_ai",
        confidence=0.0,
        data_quality=0.0,
        as_of_date=date(2026, 5, 31),
        parameter_version="valuation_params_v1",
        model_version="valuation_model_v1",
    )
    audit = CapexDecisionAuditRow(
        audit_id="audit-1",
        snapshot_id="scenario-1",
        as_of_date=date(2026, 5, 31),
        decision_type="read_only_capex_report",
        parameter_version="scenario_params_v1",
        model_version="scenario_model_v1",
        data_quality=0.75,
        reason_codes=[_reason()],
        warnings=[_warning()],
    )
    repo = CapexCycleSnapshotRepository(
        scenario_snapshots=[scenario],
        valuation_snapshots=[valuation],
        audit_rows=[audit],
        universe_metadata={"universe_id": "capex_fixture"},
    )

    assert repo.get_latest_scenario_snapshot().parameter_version == "scenario_params_v1"
    assert repo.get_latest_valuation_snapshot(asset_id="sample_ai").model_version == "valuation_model_v1"
    rows = repo.get_audit_rows(snapshot_id="scenario-1")
    assert rows[0].reason_codes[0].code == "AI_CAPEX_CYCLE_COMPUTED"
    assert repo.get_universe_metadata(as_of_date=date(2026, 5, 31))["as_of_date"] == "2026-05-31"


def test_repository_exposes_no_mutation_methods():
    method_names = [
        name
        for name, value in inspect.getmembers(CapexCycleSnapshotRepository, predicate=inspect.isfunction)
        if not name.startswith("_")
    ]
    blocked_prefixes = ("create", "insert", "update", "upsert", "delete", "save", "execute", "submit")

    assert method_names
    assert not any(name.startswith(blocked_prefixes) for name in method_names)


def test_repository_source_does_not_import_migrations_or_execution_layers():
    source = inspect.getsource(CapexCycleSnapshotRepository).lower()

    forbidden = ["migrations", "api.brokers", "api.strategy", "api.features.orders", "kis"]
    assert not [item for item in forbidden if item in source]


def _score(snapshot_id: str, as_of_date: date, *, score: float) -> CapexScoreSnapshot:
    return CapexScoreSnapshot(
        snapshot_id=snapshot_id,
        score_type="ai_capex_cycle",
        entity_id="ai_infrastructure",
        score=score,
        confidence=0.8,
        data_quality=0.75,
        as_of_date=as_of_date,
        parameter_version="params_v1",
        model_version="model_v1",
        reason_codes=[_reason()],
        warnings=[],
    )


def _reason() -> ReasonItem:
    return ReasonItem(code="AI_CAPEX_CYCLE_COMPUTED", category="feature")


def _warning() -> WarningItem:
    return WarningItem(code="LOW_DATA_QUALITY", severity="WARNING", source="feature", message="review required")
