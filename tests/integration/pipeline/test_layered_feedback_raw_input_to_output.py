from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from api.data.strategy_data_readers import SqliteMacroSnapshotReader
from api.db.initialize import initialize_database
from api.domain.decision_state import LayerOutputEnvelope
from api.score_pipeline.adapters.macro_distribution_adapter import MacroDistributionAdapter
from api.score_pipeline.orchestrator import DecisionOrchestrator
from api.score_pipeline.orchestrator_contracts import DecisionLayerId, DecisionRequest, DecisionRunMode


def test_raw_macro_input_to_layered_feedback_output(tmp_path, monkeypatch):
    db_path = str(tmp_path / "layered_feedback.db")
    monkeypatch.setattr("api.db.connection.DB_PATH", db_path)
    initialize_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    decision_date = date(2024, 3, 10)
    _seed_macro_fixture(conn)

    macro_snapshot = SqliteMacroSnapshotReader(conn).read_macro_snapshot(decision_date)
    macro_distribution = MacroDistributionAdapter().adapt(macro_snapshot, previous_score=60)

    assert macro_snapshot.get_value("VIXCLS") == 40.0
    assert macro_distribution.dominant_regime == "volatility_stress"
    assert round(sum(macro_distribution.distribution.values()), 6) == 1.0

    orchestrator = DecisionOrchestrator(
        [
            _LayerRunner(
                DecisionLayerId.DATA,
                payload={"macro_source": "fixture", "vix": macro_snapshot.get_value("VIXCLS")},
                warnings=("LOW_DATA_QUALITY_REVIEW_REQUIRED",),
            ),
            _LayerRunner(
                DecisionLayerId.MACRO,
                payload=asdict(macro_distribution),
            ),
        ]
    )
    result = orchestrator.run(
        DecisionRequest(
            run_id="layered-feedback-run",
            as_of_date=decision_date,
            mode=DecisionRunMode.REVIEW_ONLY,
            raw_inputs={"source": "sqlite_fixture"},
            portfolio_state={"mode": "simulation"},
            account_state={"account_type": "SIMULATED"},
            parameter_version="fixture-params",
        )
    )

    assert result.execution_allowed is False
    assert result.state_snapshot.feedback_signals
    next_run_input = result.state_snapshot.to_next_run_input()
    assert next_run_input["feedback_signals"][0]["recommended_action"] == "REVIEW_REQUIRED"
    assert _contains_forbidden_output_key(asdict(result)) is False


def _seed_macro_fixture(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?, ?, ?, ?, ?)",
        [
            ("VIXCLS", 40.0, "pt", "2024-03-08", "known"),
            ("VIXCLS", 12.0, "pt", "2024-03-15", "future"),
            ("ISM_PMI", 44.0, "pt", "2024-03-08", "known"),
        ],
    )
    conn.commit()


@dataclass
class _LayerRunner:
    layer_id: str
    payload: dict[str, Any]
    warnings: tuple[str, ...] = ()

    def run(self, request: DecisionRequest) -> LayerOutputEnvelope:
        return LayerOutputEnvelope(
            layer=self.layer_id,
            output_type="FixtureLayerOutput",
            as_of_date=request.as_of_date,
            payload=self.payload,
            warnings=self.warnings,
        )


def _contains_forbidden_output_key(value: Any) -> bool:
    forbidden = {"broker", "kis", "submit", "execute", "order_submission"}
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(term in normalized for term in forbidden):
                return True
            if _contains_forbidden_output_key(nested):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_forbidden_output_key(item) for item in value)
    return False
