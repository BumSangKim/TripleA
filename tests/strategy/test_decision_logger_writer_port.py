from __future__ import annotations

from datetime import date

from api.domain.strategy_inputs import StrategyDecisionLogInput
from api.strategy.decision_logger import log_strategy_decision


class FakeWriter:
    def __init__(self):
        self.calls: list[tuple[StrategyDecisionLogInput, bool]] = []

    def write_decision_log(
        self,
        payload: StrategyDecisionLogInput,
        *,
        enabled: bool = True,
    ) -> bool:
        self.calls.append((payload, enabled))
        return enabled


def test_decision_logger_builds_semantic_payload_for_writer():
    writer = FakeWriter()

    result = log_strategy_decision(
        writer,
        enabled=True,
        decision_id="d1",
        snapshot_id="s1",
        as_of_date=date(2026, 5, 27),
        decision_type="backtest_allocation",
        payload={"final_weights": {"SPY": 1.0}},
        reason_codes=["ok"],
        warnings=["review"],
    )

    assert result is True
    payload, enabled = writer.calls[0]
    assert enabled is True
    assert payload.decision_id == "d1"
    assert payload.snapshot_id == "s1"
    assert payload.as_of_date == date(2026, 5, 27)
    assert payload.decision_type == "backtest_allocation"
    assert payload.payload == {"final_weights": {"SPY": 1.0}}
    assert payload.reason_codes == ["ok"]
    assert payload.warnings == ["review"]


def test_decision_logger_disabled_does_not_call_writer():
    writer = FakeWriter()

    result = log_strategy_decision(
        writer,
        enabled=False,
        decision_id="d0",
        as_of_date=date(2026, 5, 27),
        decision_type="backtest_allocation",
        payload={},
    )

    assert result is False
    assert writer.calls == []


def test_decision_logger_missing_writer_is_conservative_noop():
    result = log_strategy_decision(
        None,
        enabled=True,
        decision_id="d0",
        as_of_date=date(2026, 5, 27),
        decision_type="backtest_allocation",
        payload={},
    )

    assert result is False

