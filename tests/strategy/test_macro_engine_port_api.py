from __future__ import annotations

from datetime import date

import api.strategy.macro_engine as macro_engine_module
from api.domain.strategy_inputs import MacroIndicatorInput, MacroSnapshotInput
from api.strategy.macro_engine import MacroEngine, evaluate_macro_snapshot


class FakeMacroReader:
    def __init__(self, snapshot: MacroSnapshotInput):
        self.snapshot = snapshot
        self.read_dates: list[date] = []

    def read_macro_snapshot(self, as_of_date: date) -> MacroSnapshotInput:
        self.read_dates.append(as_of_date)
        return self.snapshot


class FilteringFakeMacroReader:
    def __init__(self, values: list[tuple[date, float]]):
        self.values = values

    def read_macro_snapshot(self, as_of_date: date) -> MacroSnapshotInput:
        visible = [item for item in self.values if item[0] <= as_of_date]
        indicators = {}
        if visible:
            data_date, value = visible[-1]
            indicators["VIXCLS"] = MacroIndicatorInput(
                indicator="VIXCLS",
                value=value,
                unit="pt",
                data_date=data_date,
                source="fake",
            )
        return MacroSnapshotInput(as_of_date=as_of_date, indicators=indicators)


def _snapshot() -> MacroSnapshotInput:
    return MacroSnapshotInput(
        as_of_date=date(2024, 1, 3),
        indicators={
            "VIXCLS": MacroIndicatorInput(
                indicator="VIXCLS",
                value=38.0,
                unit="pt",
                data_date=date(2024, 1, 2),
                source="fake",
            ),
            "ISM_PMI": MacroIndicatorInput(
                indicator="ISM_PMI",
                value=44.0,
                unit="pt",
                data_date=date(2024, 1, 2),
                source="fake",
            ),
        },
    )


def test_macro_engine_reader_path_matches_evaluate_macro_snapshot():
    snapshot = _snapshot()
    reader = FakeMacroReader(snapshot)

    decision = MacroEngine.from_reader(reader).evaluate(date(2024, 1, 3))
    expected = evaluate_macro_snapshot(snapshot)

    assert decision == expected
    assert reader.read_dates == [date(2024, 1, 3)]


def test_macro_engine_reader_path_empty_snapshot_is_neutral_safe():
    decision = MacroEngine.from_reader(
        FakeMacroReader(MacroSnapshotInput(as_of_date=date(2024, 1, 3)))
    ).evaluate(date(2024, 1, 3))

    assert decision.regime == "neutral"
    assert decision.score == 50
    assert "neutral regime" in decision.reasons[0]


def test_macro_reader_documents_point_in_time_filtering_boundary():
    reader = FilteringFakeMacroReader([
        (date(2024, 1, 2), 15.0),
        (date(2024, 1, 10), 40.0),
    ])

    decision = MacroEngine.from_reader(reader).evaluate(date(2024, 1, 5))

    assert decision.indicators["VIXCLS"] == 15.0
    assert decision.regime in {"neutral", "risk_on"}


def test_macro_engine_reader_path_does_not_call_legacy_root_service(monkeypatch):
    def fail_legacy_call(*args, **kwargs):
        raise AssertionError("reader path must not call get_macro_snapshot")

    monkeypatch.setattr(macro_engine_module, "get_macro_snapshot", fail_legacy_call)

    decision = MacroEngine.from_reader(FakeMacroReader(_snapshot())).evaluate(date(2024, 1, 3))

    assert decision.regime == "risk_off"

