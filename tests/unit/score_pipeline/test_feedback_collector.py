from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from api.domain.decision_feedback import FeedbackSeverity
from api.score_pipeline.contracts import ConstraintResult, DecisionWarning, ReasonCode
from api.score_pipeline.feedback import FeedbackCollector


def test_blocked_constraint_result_produces_blocking_feedback():
    result = ConstraintResult(
        passed=False,
        blocked=True,
        reason_codes=[ReasonCode("RISKY_ASSET_LIMIT_BLOCKED", "constraint")],
        conservative_action="REVIEW_REQUIRED",
    )

    signals = FeedbackCollector().collect(result, as_of_date=date(2024, 3, 10))

    assert isinstance(signals, tuple)
    assert len(signals) == 1
    assert signals[0].severity == FeedbackSeverity.BLOCK
    assert signals[0].recommended_action == "REVIEW_REQUIRED"


def test_low_data_quality_warning_produces_review_required_feedback():
    warning = DecisionWarning(
        code="LOW_DATA_QUALITY_BLOCKS_RISK_INCREASE",
        severity="WARNING",
        source="risk",
        message="data quality too low",
    )

    signals = FeedbackCollector().collect(warning, as_of_date=date(2024, 3, 10))

    assert len(signals) == 1
    assert signals[0].severity == FeedbackSeverity.REVIEW_REQUIRED
    assert signals[0].recommended_action == "REVIEW_REQUIRED"


def test_blocker_warning_produces_blocking_feedback():
    warning = DecisionWarning(
        code="HARD_CONSTRAINT_ZERO_TARGET",
        severity="BLOCKER",
        source="constraint",
        message="hard constraint blocked risk increase",
    )

    signals = FeedbackCollector().collect(warning, as_of_date=date(2024, 3, 10))

    assert len(signals) == 1
    assert signals[0].severity == FeedbackSeverity.BLOCK


def test_unknown_object_ignored_safely():
    signals = FeedbackCollector().collect(object(), as_of_date=date(2024, 3, 10))

    assert signals == ()


def test_output_warnings_are_collected_without_calling_engines():
    class OutputWithWarnings:
        warnings = (
            DecisionWarning(
                code="LOW_DATA_QUALITY_REVIEW_REQUIRED",
                severity="WARNING",
                source="rebalancing",
                message="low data quality requires review",
            ),
        )

    signals = FeedbackCollector().collect(OutputWithWarnings(), as_of_date=date(2024, 3, 10))

    assert len(signals) == 1
    assert signals[0].recommended_action == "REVIEW_REQUIRED"


def test_feedback_collector_module_stays_pure():
    path = Path("api/score_pipeline/feedback.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden_modules = {"fastapi", "starlette", "sqlite3", "api.db", "api.features", "api.strategy"}

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert imports.isdisjoint(forbidden_modules)
