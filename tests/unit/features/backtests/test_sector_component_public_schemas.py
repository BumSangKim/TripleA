from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.features.backtests.schemas import (
    BacktestRunRequest,
    SectorComponentComparisonRowResponse,
    SectorComponentRunRequest,
    SectorComponentRunResponse,
    SectorComponentScopePayload,
    SectorComponentUiMetadataResponse,
)


def test_all_request_validation() -> None:
    request = SectorComponentRunRequest(sectorScope={"mode": "all", "sectorId": None})

    assert request.sectorScope.mode == "all"
    assert request.sectorScope.sectorId is None


def test_single_request_validation() -> None:
    request = SectorComponentRunRequest(sectorScope={"mode": "single", "sectorId": "SEMICONDUCTOR"})

    assert request.sectorScope.mode == "single"
    assert request.sectorScope.sectorId == "SEMICONDUCTOR"


def test_single_without_sector_id_fails() -> None:
    with pytest.raises(ValidationError, match="requires sectorId"):
        SectorComponentRunRequest(sectorScope={"mode": "single"})


def test_all_with_sector_id_fails() -> None:
    with pytest.raises(ValidationError, match="must not include sectorId"):
        SectorComponentScopePayload(mode="all", sectorId="SEMICONDUCTOR")


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        SectorComponentRunRequest(sectorScope={"mode": "all"}, unexpected=True)
    with pytest.raises(ValidationError):
        SectorComponentRunRequest(sectorScope={"mode": "all", "extra": "x"})


def test_run_response_minimum_payload_serializes() -> None:
    response = SectorComponentRunResponse(
        ok=True,
        sectorScope={"mode": "single", "sectorId": "SEMICONDUCTOR"},
        parameterVersion="p1",
        modelVersion="m1",
        dataSnapshotId="scope-1",
        status="OK",
        comparisonRows=[
            SectorComponentComparisonRowResponse(
                sectorId="SEMICONDUCTOR",
                displayName="Semiconductor",
                portfolioId="sector_semiconductor_current_v1",
                status="OK",
                totalReturn=0.01,
                observationCount=3,
                reasonCodes=["SECTOR_COMPONENT_SCOPE_RESULT"],
            )
        ],
        reasonCodes=["SECTOR_COMPONENT_SCOPE_COMPLETED"],
    )

    payload = response.model_dump()

    assert payload["sectorScope"] == {"mode": "single", "sectorId": "SEMICONDUCTOR"}
    assert payload["comparisonRows"][0]["sectorId"] == "SEMICONDUCTOR"
    assert payload["semantics"] == "independent_enabled_sector_backtests"


def test_ui_metadata_response_serializes() -> None:
    response = SectorComponentUiMetadataResponse(
        ok=True,
        parameterVersion="p1",
        modelVersion="m1",
        allSectorOption={"label": "전체 섹터", "value": "ALL", "sectorScope": {"mode": "all"}},
        sectorOptions=[
            {
                "label": "Semiconductor",
                "value": "SEMICONDUCTOR",
                "sectorId": "SEMICONDUCTOR",
                "portfolioId": "sector_semiconductor_current_v1",
                "enabled": True,
                "assetCount": 2,
                "reasonCodes": ["SECTOR_PORTFOLIO_CONFIG_LOADED"],
            }
        ],
        reasonCodes=["SECTOR_COMPONENT_UI_METADATA_BUILT"],
    )

    payload = response.model_dump()

    assert payload["allSectorOption"]["value"] == "ALL"
    assert payload["sectorOptions"][0]["assetCount"] == 2


def test_existing_backtest_run_request_regression() -> None:
    request = BacktestRunRequest(
        startDate="2020-01-01",
        endDate="2024-12-31",
        initialCapital=100000000,
        rebalanceFrequency="monthly",
    )

    assert request.strategyMode == "triplea_dynamic"
    assert request.riskProfile == "balanced"
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            startDate="2020-01-01",
            endDate="2024-12-31",
            initialCapital=100000000,
            rebalanceFrequency="monthly",
            sectorScope={"mode": "all"},
        )
