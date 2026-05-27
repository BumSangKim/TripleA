from datetime import UTC, date, datetime

import pytest
import yaml

from api.score_pipeline.contracts import (
    ConservativeAction,
    ConstraintResult,
    DataQualityMetadata,
    DecisionLogRecord,
    DecisionWarning,
    FeatureOutput,
    PipelineContractError,
    ReasonCode,
    ScoreOutput,
    to_json,
)
from api.score_pipeline.parameters import ParameterRegistry


def _quality():
    return DataQualityMetadata(
        source="fixture",
        as_of_date=date(2026, 5, 27),
        updated_at=datetime(2026, 5, 27, tzinfo=UTC),
        quality_score=0.9,
        missing_ratio=0.0,
    )


def test_contract_objects_are_serializable():
    reason = ReasonCode("FEATURE_OK", "feature")
    warning = DecisionWarning("LOW_CONFIDENCE", "WARNING", "test", "confidence is low")
    feature = FeatureOutput(
        "momentum_63d",
        "Momentum 63D",
        "SPY",
        "asset",
        0.12,
        0.62,
        0.8,
        _quality(),
        date(2026, 5, 27),
        "fixture",
        "score_pipeline_v1",
        "feature_v1",
        [reason],
        [warning],
    )
    payload = to_json(feature)
    assert "momentum_63d" in payload
    assert "LOW_CONFIDENCE" in payload


def test_score_range_validation_and_missing_required_field():
    with pytest.raises(PipelineContractError, match="score"):
        ScoreOutput("", "SPY", "asset", 1.2, None, 0, 1, 1, 1, 1, date(2026, 5, 27), "p", "m")

    score = ScoreOutput(
        "score:SPY",
        "SPY",
        "asset",
        0.6,
        0.5,
        0.1,
        0.8,
        0.9,
        0.9,
        0.2,
        date(2026, 5, 27),
        "p",
        "m",
    )
    assert score.score_change == pytest.approx(0.1)


def test_conservative_fallback_enum_and_constraint_result():
    assert ConservativeAction.REVIEW_REQUIRED in ConservativeAction.values()
    result = ConstraintResult(passed=False, blocked=True, conservative_action=ConservativeAction.REVIEW_REQUIRED)
    assert result.blocked is True


def test_decision_log_downstream_compatibility_smoke():
    log = DecisionLogRecord(
        date=date(2026, 5, 27),
        data_snapshot_id="snap-1",
        parameter_version="score_pipeline_v1",
        model_version="pipeline_v1",
        macro_scores={"neutral": 0.5},
        sector_scores={"SPY": 0.6},
        risk_budget_scores={"risk": 0.4},
        target_weights={"SPY": 0.1},
        current_weights={"SPY": 0.08},
        rebalance_scores={"SPY": 0.2},
        account_constraints={"passed": True},
        decision="HOLD",
        adjustment_intensity=0.2,
        reason_codes=[ReasonCode("SCORE_FLOW", "pipeline")],
        warnings=[],
    )
    assert "SCORE_FLOW" in to_json(log)


def test_valid_parameter_load_and_version_propagation():
    registry = ParameterRegistry.from_yaml()
    lookup = registry.get("ema_span", as_of_date=date(2026, 5, 27), expected_type=int)
    assert lookup.value == 5
    assert lookup.version_ref.version == "score_pipeline_v1"
    assert registry.parameter_version_for(["ema_span", "turnover_limit"], date(2026, 5, 27)) == "score_pipeline_v1"


def test_missing_and_invalid_parameter_fallback(tmp_path):
    path = tmp_path / "params.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "fallback_policy": "REVIEW_REQUIRED",
                "parameters": [
                    {
                        "name": "ema_span",
                        "value": "bad",
                        "version": "v1",
                        "valid_from": "2021-01-01",
                        "valid_to": None,
                        "source": "fixture",
                        "reason": "test",
                        "approved": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    registry = ParameterRegistry.from_yaml(path)
    invalid = registry.get("ema_span", as_of_date=date(2026, 5, 27), expected_type=int)
    missing = registry.get("does_not_exist", as_of_date=date(2026, 5, 27))
    expired = registry.get("ema_span", as_of_date=date(2020, 12, 31))
    assert invalid.conservative_action == "REVIEW_REQUIRED"
    assert missing.conservative_action == "REVIEW_REQUIRED"
    assert expired.conservative_action == "REVIEW_REQUIRED"


def test_no_aggressive_fallback_parameters():
    registry = ParameterRegistry.from_yaml()
    assert registry.fallback_policy in ConservativeAction.values()
