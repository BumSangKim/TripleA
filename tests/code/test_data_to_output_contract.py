from __future__ import annotations

import copy
import json
import socket
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from api.score_pipeline.data_quality import RawDataPoint, SnapshotBuilder
from api.score_pipeline.engines import (
    AllocationEngine,
    MacroRegimeEngine,
    RebalancingEngine,
    RiskBudgetEngine,
    SectorDefinition,
    SectorScoringEngine,
)
from api.score_pipeline.features import FeatureRegistry, PriceMomentumFeaturePlugin
from api.score_pipeline.parameters import ParameterRegistry
from api.score_pipeline.scoring import ScoreRegistry


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "pipeline"
CONSERVATIVE_ACTIONS = {"NO_ACTION", "HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}
RISK_INCREASING_ACTIONS = {"BUY", "LIMITED_INCREASE"}


@pytest.fixture(autouse=True)
def block_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked_connect(*args, **kwargs):
        raise AssertionError("network calls are forbidden in deterministic code tests")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)


def test_fixture_raw_input_to_local_decision_output_is_deterministic():
    raw_data = _load_fixture("sample_raw_data.json")
    account_state = _load_fixture("sample_account_state.json")
    positions = _load_fixture("sample_current_positions.json")

    first = _run_data_to_output(raw_data, account_state, positions)
    second = _run_data_to_output(raw_data, account_state, positions)

    assert first == second
    assert first["stages"] == [
        "raw_input_loaded",
        "data_snapshot_built",
        "features_calculated",
        "scores_calculated",
        "macro_evaluated",
        "sector_scored",
        "risk_budget_checked",
        "allocation_targeted",
        "rebalance_planned",
        "decision_snapshot_built",
    ]
    assert first["decision_snapshot"]["as_of_date"] == raw_data["decision_date"]
    assert first["decision_snapshot"]["data_snapshot_id"] == "simplification:data-to-output"
    assert first["decision_snapshot"]["parameter_version"]
    assert first["decision_snapshot"]["model_version"] == "simplified_decision_snapshot_v1"
    assert first["decision_snapshot"]["reason_codes"]
    assert first["decision_snapshot"]["action"] in CONSERVATIVE_ACTIONS
    _assert_no_live_execution_surface(first)


def test_missing_required_input_returns_review_required_without_risk_increase():
    raw_data = _load_fixture("sample_raw_data.json")
    raw_data["rows"] = [row for row in raw_data["rows"] if row["kind"] != "price"]

    output = _run_data_to_output(raw_data, _load_fixture("sample_account_state.json"), _load_fixture("sample_current_positions.json"))

    assert output["decision_snapshot"]["action"] in {"REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}
    assert "FEATURE_FALLBACK_NEUTRAL" in output["decision_snapshot"]["warnings"]
    assert output["rebalance_plan"]["risk_increase_allowed"] is False
    _assert_no_live_execution_surface(output)


def test_stale_input_uses_conservative_output_action():
    raw_data = _load_fixture("sample_raw_data.json")
    for row in raw_data["rows"]:
        row["as_of_date"] = "2026-04-01"
        row["available_at"] = "2026-04-01T00:00:00+00:00"

    output = _run_data_to_output(raw_data, _load_fixture("sample_account_state.json"), _load_fixture("sample_current_positions.json"))

    assert output["decision_snapshot"]["action"] in {"HOLD", "REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}
    assert "STALE_DATA" in output["decision_snapshot"]["warnings"]
    assert output["rebalance_plan"]["risk_increase_allowed"] is False


def test_invalid_parameter_registry_fails_safely():
    output = _run_data_to_output(
        _load_fixture("sample_raw_data.json"),
        _load_fixture("sample_account_state.json"),
        _load_fixture("sample_current_positions.json"),
        registry=ParameterRegistry([]),
    )

    assert output["decision_snapshot"]["action"] in {"REVIEW_REQUIRED", "RISK_REDUCE_ONLY"}
    assert "unavailable" in output["decision_snapshot"]["parameter_version"]
    assert output["rebalance_plan"]["risk_increase_allowed"] is False


def test_output_contract_has_traceability_and_no_secret_dependency(monkeypatch: pytest.MonkeyPatch):
    for key in ("KIS_APP_KEY", "APP_KEY", "APP_SECRET", "ACCESS_TOKEN", "API_KEY"):
        monkeypatch.delenv(key, raising=False)

    output = _run_data_to_output(
        _load_fixture("sample_raw_data.json"),
        _load_fixture("sample_account_state.json"),
        _load_fixture("sample_current_positions.json"),
    )

    decision = output["decision_snapshot"]
    assert {"as_of_date", "data_snapshot_id", "parameter_version", "model_version", "reason_codes", "warnings"} <= set(decision)
    assert output["rebalance_plan"]["items"][0]["asset_id"] == "SAMPLE_US_EQUITY"
    assert output["rebalance_plan"]["items"][0]["execution_allowed"] is False


def _run_data_to_output(
    raw_data: dict[str, Any],
    account_state: dict[str, Any],
    positions: dict[str, Any],
    *,
    registry: ParameterRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or ParameterRegistry.from_yaml()
    as_of_date = date.fromisoformat(raw_data["decision_date"])
    snapshot = SnapshotBuilder().build("simplification:data-to-output", as_of_date, _raw_points(raw_data))
    feature_registry = FeatureRegistry()
    feature_registry.register(PriceMomentumFeaturePlugin(asset_id="SAMPLE_US_EQUITY"))
    features = feature_registry.run_enabled(snapshot, registry)
    scores = ScoreRegistry().calculate_all(features, registry)
    macro = MacroRegimeEngine().evaluate(scores, registry, as_of_date=as_of_date)
    sector = SectorScoringEngine(
        {
            "SAMPLE_SECTOR": SectorDefinition(
                sector_id="SAMPLE_SECTOR",
                enabled=True,
                component_weights={"macro_fit": 0.5, "data_quality": 0.5},
            )
        }
    ).score(sector_id="SAMPLE_SECTOR", macro=macro, components={}, as_of_date=as_of_date, registry=registry, previous_score=0.45)
    account = _account(account_state, "fixture_general_account")
    current_weight = _position_weight(positions, account["account_id"], "SAMPLE_US_EQUITY")
    risk = RiskBudgetEngine().evaluate(
        account_type="taxable",
        current_weights={"SAMPLE_US_EQUITY": current_weight},
        risky_assets={"SAMPLE_US_EQUITY"},
        volatility=0.10,
        drawdown=0.05,
        data_quality=sector.data_quality,
        registry=registry,
        as_of_date=as_of_date,
    )
    target = AllocationEngine().allocate(
        asset_id="SAMPLE_US_EQUITY",
        sector_score=sector,
        macro=macro,
        risk=risk,
        previous_target=current_weight,
        registry=registry,
    )
    rebalance = RebalancingEngine().decide(
        target=target,
        current_weight=current_weight,
        sector_score=sector,
        risk=risk,
        cash_available_score=0.5,
        turnover_penalty=0.1,
    )
    warnings = _warning_codes(snapshot.warnings, *[item.warnings for item in features], [*risk.warnings, *target.warnings, *rebalance.warnings])
    reason_codes = _reason_codes(macro.reason_codes, sector.reason_codes, risk.reason_codes, target.reason_codes, rebalance.reason_codes)
    parameter_version = "+".join(
        sorted(
            {
                *(item.parameter_version for item in features),
                *(item.parameter_version for item in scores),
                macro.parameter_version,
                sector.parameter_version,
                risk.parameter_version,
                target.parameter_version,
                rebalance.parameter_version,
            }
        )
    )
    action = _safe_action(rebalance.action, warnings=warnings, parameter_version=parameter_version, risk_blocked=risk.constraint_result.blocked)
    if action == "REVIEW_REQUIRED" and "REVIEW_REQUIRED_OUTPUT" not in warnings:
        warnings.append("REVIEW_REQUIRED_OUTPUT")
    risk_increase_allowed = action not in {"REVIEW_REQUIRED", "HOLD", "NO_ACTION", "RISK_REDUCE_ONLY"} and not risk.constraint_result.blocked
    return {
        "stages": [
            "raw_input_loaded",
            "data_snapshot_built",
            "features_calculated",
            "scores_calculated",
            "macro_evaluated",
            "sector_scored",
            "risk_budget_checked",
            "allocation_targeted",
            "rebalance_planned",
            "decision_snapshot_built",
        ],
        "decision_snapshot": {
            "as_of_date": as_of_date.isoformat(),
            "data_snapshot_id": snapshot.snapshot_id,
            "data_quality": sector.data_quality,
            "parameter_version": parameter_version,
            "model_version": "simplified_decision_snapshot_v1",
            "action": action,
            "reason_codes": reason_codes,
            "warnings": sorted(set(warnings)),
        },
        "rebalance_plan": {
            "as_of_date": as_of_date.isoformat(),
            "data_snapshot_id": snapshot.snapshot_id,
            "parameter_version": parameter_version,
            "model_version": "simplified_rebalance_plan_v1",
            "risk_increase_allowed": risk_increase_allowed,
            "items": [
                {
                    "asset_id": rebalance.asset_id,
                    "current_weight": rebalance.current_weight,
                    "target_weight": rebalance.target_weight,
                    "action": action,
                    "reason_codes": reason_codes,
                    "warnings": sorted(set(warnings)),
                    "execution_allowed": False,
                }
            ],
        },
    }


def _safe_action(action: str, *, warnings: list[str], parameter_version: str, risk_blocked: bool) -> str:
    if risk_blocked:
        return "RISK_REDUCE_ONLY"
    if "unavailable" in parameter_version or any(code in warnings for code in ("MISSING_DATA", "STALE_DATA", "FEATURE_FALLBACK_NEUTRAL")):
        return "REVIEW_REQUIRED"
    if action in RISK_INCREASING_ACTIONS:
        return "REVIEW_REQUIRED"
    if action in CONSERVATIVE_ACTIONS:
        return action
    return "HOLD"


def _raw_points(raw_data: dict[str, Any]) -> list[RawDataPoint]:
    points: list[RawDataPoint] = []
    price_row: dict[str, Any] | None = None
    for row in raw_data["rows"]:
        available_at = datetime.fromisoformat(row["available_at"])
        as_of_date = date.fromisoformat(row["as_of_date"])
        points.append(
            RawDataPoint(
                key=f"{row['kind']}:{row['metric']}",
                value=float(row["value"]),
                source=row["source"],
                as_of_date=as_of_date,
                available_at=available_at,
                updated_at=available_at,
            )
        )
        if row["kind"] == "price":
            price_row = row
    if price_row is not None:
        available_at = datetime.fromisoformat(price_row["available_at"])
        as_of_date = date.fromisoformat(price_row["as_of_date"])
        for key in ("price_start", "price_end"):
            points.append(
                RawDataPoint(
                    key=key,
                    value=float(price_row["value"]),
                    source=price_row["source"],
                    as_of_date=as_of_date,
                    available_at=available_at,
                    updated_at=available_at,
                )
            )
    return points


def _load_fixture(name: str) -> dict[str, Any]:
    return copy.deepcopy(json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8")))


def _account(account_state: dict[str, Any], account_id: str) -> dict[str, Any]:
    return next(account for account in account_state["accounts"] if account["account_id"] == account_id)


def _position_weight(positions: dict[str, Any], account_id: str, asset_id: str) -> float:
    for position in positions["positions"]:
        if position["account_id"] == account_id and position["asset_id"] == asset_id:
            return float(position["current_weight"])
    return 0.0


def _warning_codes(*warning_groups) -> list[str]:
    codes: list[str] = []
    for group in warning_groups:
        for warning in group:
            codes.append(warning.code)
    return codes


def _reason_codes(*reason_groups) -> list[str]:
    codes: list[str] = []
    for group in reason_groups:
        for reason in group:
            codes.append(reason.code)
    return sorted(set(codes))


def _assert_no_live_execution_surface(output: dict[str, Any]) -> None:
    payload = json.dumps(output, sort_keys=True)
    forbidden = ("orderDraftId", "brokerOrderPayload", "LIVE_EXECUTE", "AUTO_EXECUTE", "FORCE_REBALANCE")
    assert not any(term in payload for term in forbidden)
    assert all(item["execution_allowed"] is False for item in output["rebalance_plan"]["items"])
