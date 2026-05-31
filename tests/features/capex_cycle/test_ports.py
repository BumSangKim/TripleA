from __future__ import annotations

import inspect
from datetime import date

from api.features.capex_cycle.ports import ICapexCycleRepository, ICapexCycleService
from api.features.capex_cycle.schemas import CapexCycleScoreResponse, CapexScenarioResponse, CapexValuationResponse


def _score() -> CapexCycleScoreResponse:
    return CapexCycleScoreResponse(
        feature_id="ai_capex_cycle",
        entity_id="ai_capex_universe",
        score=0.6,
        confidence=0.8,
        data_quality=0.7,
        as_of_date=date(2026, 5, 31),
        parameter_version="params_v1",
        model_version="model_v1",
    )


def _scenario() -> CapexScenarioResponse:
    return CapexScenarioResponse(
        scenario_id="capex_scenario_distribution",
        score=0.5,
        confidence=0.8,
        data_quality=0.7,
        scenario_distribution={"ai_buildout_continues": 0.5, "credit_stress": 0.1},
        dominant_scenario="ai_buildout_continues",
        as_of_date=date(2026, 5, 31),
        parameter_version="params_v1",
        model_version="model_v1",
    )


def _valuation() -> CapexValuationResponse:
    return CapexValuationResponse(
        asset_id="sample_ai_infra",
        score=0.55,
        confidence=0.8,
        data_quality=0.7,
        fair_value=None,
        current_price=None,
        fair_value_ratio=None,
        as_of_date=date(2026, 5, 31),
        parameter_version="params_v1",
        model_version="model_v1",
    )


def test_fake_repository_conforms_to_readonly_protocol():
    class FakeRepository:
        def get_latest_score_snapshot(self, *, as_of_date=None, asset_id=None):
            return _score()

        def get_latest_scenario_snapshot(self, *, as_of_date=None):
            return _scenario()

        def get_latest_valuation_snapshot(self, *, asset_id, as_of_date=None):
            return _valuation()

        def get_universe_metadata(self, *, as_of_date=None):
            return {"universe_id": "capex_fixture"}

    repo = FakeRepository()

    assert isinstance(repo, ICapexCycleRepository)
    assert repo.get_latest_score_snapshot(as_of_date=date(2026, 5, 31)).score == 0.6
    assert repo.get_universe_metadata()["universe_id"] == "capex_fixture"


def test_fake_service_conforms_to_readonly_protocol():
    class FakeService:
        def get_scores(self, *, as_of_date=None, asset_id=None):
            return [_score()]

        def get_scenario(self, *, as_of_date=None):
            return _scenario()

        def get_valuation(self, *, asset_id, as_of_date=None):
            return _valuation()

    service = FakeService()

    assert isinstance(service, ICapexCycleService)
    assert service.get_scores()[0].feature_id == "ai_capex_cycle"
    assert service.get_scenario().dominant_scenario == "ai_buildout_continues"
    assert service.get_valuation(asset_id="sample_ai_infra").asset_id == "sample_ai_infra"


def test_repository_methods_are_readonly_and_accept_as_of_date():
    method_names = [
        name
        for name, value in inspect.getmembers(ICapexCycleRepository)
        if inspect.isfunction(value) and not name.startswith("_")
    ]
    forbidden_prefixes = ("create", "update", "upsert", "delete", "save", "execute", "submit", "order")

    assert method_names
    assert all(name.startswith(("get_", "list_")) for name in method_names)
    assert not any(name.startswith(forbidden_prefixes) for name in method_names)
    assert "as_of_date" in inspect.signature(ICapexCycleRepository.get_latest_score_snapshot).parameters
    assert "as_of_date" in inspect.signature(ICapexCycleRepository.get_latest_scenario_snapshot).parameters
    assert "as_of_date" in inspect.signature(ICapexCycleRepository.get_latest_valuation_snapshot).parameters


def test_ports_do_not_expose_order_or_execution_methods():
    source = inspect.getsource(ICapexCycleRepository) + inspect.getsource(ICapexCycleService)
    blocked_terms = ("execute", "submit", "broker", "kis", "target_weight", "order_candidate")

    for term in blocked_terms:
        assert term not in source.lower()
