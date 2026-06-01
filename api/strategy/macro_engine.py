from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date

from api.domain.strategy_inputs import MacroSnapshotInput
from api.macro_data_service import MacroSnapshot, get_macro_snapshot
from api.strategy.data_ports import MacroSnapshotReader


@dataclass(frozen=True)
class MacroRegimeDecision:
    as_of_date: date
    regime: str
    score: int
    indicators: dict[str, float]
    reasons: list[str] = field(default_factory=list)


class MacroEngine:
    def __init__(
        self,
        conn: sqlite3.Connection | None = None,
        *,
        reader: MacroSnapshotReader | None = None,
    ):
        self.conn = conn
        self.reader = reader

    @classmethod
    def from_reader(cls, reader: MacroSnapshotReader) -> "MacroEngine":
        return cls(reader=reader)

    def evaluate(self, as_of_date: date) -> MacroRegimeDecision:
        if self.reader is not None:
            snapshot = self.reader.read_macro_snapshot(as_of_date)
        elif self.conn is not None:
            snapshot = get_macro_snapshot(self.conn, as_of_date)
        else:
            snapshot = MacroSnapshotInput(as_of_date=as_of_date)
        return evaluate_macro_snapshot(snapshot)


def evaluate_macro_snapshot(snapshot: MacroSnapshot | MacroSnapshotInput) -> MacroRegimeDecision:
    indicators = {
        key: item.value
        for key, item in snapshot.indicators.items()
    }
    score = 50
    reasons: list[str] = []

    vix = snapshot.get_value("VIXCLS", "VIX")
    if vix is not None:
        if vix >= 35:
            score -= 35
            reasons.append(f"VIX {vix:.1f} signals risk_off stress")
        elif vix >= 25:
            score -= 20
            reasons.append(f"VIX {vix:.1f} signals cautious volatility")
        elif vix >= 20:
            score -= 8
            reasons.append(f"VIX {vix:.1f} is mildly elevated")
        elif vix <= 14:
            score += 10
            reasons.append(f"VIX {vix:.1f} supports risk_on")

    pmi = snapshot.get_value("ISM_PMI", "PMI")
    if pmi is not None:
        if pmi < 45:
            score -= 15
            reasons.append(f"PMI {pmi:.1f} signals contraction")
        elif pmi < 50:
            score -= 6
            reasons.append(f"PMI {pmi:.1f} is below expansion threshold")
        elif pmi >= 53:
            score += 8
            reasons.append(f"PMI {pmi:.1f} supports expansion")

    curve = snapshot.get_value("T10Y2Y")
    if curve is not None:
        if curve < -0.5:
            score -= 10
            reasons.append(f"Yield curve spread {curve:.2f} is deeply inverted")
        elif curve < 0:
            score -= 5
            reasons.append(f"Yield curve spread {curve:.2f} is inverted")

    unemployment = snapshot.get_value("UNRATE", "UNEMPLOYMENT")
    if unemployment is not None:
        if unemployment >= 5.5:
            score -= 8
            reasons.append(f"Unemployment {unemployment:.1f}% weakens macro score")
        elif unemployment <= 4.0:
            score += 4
            reasons.append(f"Unemployment {unemployment:.1f}% supports labor strength")

    bounded_score = max(0, min(100, round(score)))
    regime = _regime_from_score(bounded_score, vix)
    if not reasons:
        reasons.append("No macro stress signal available; neutral regime")

    return MacroRegimeDecision(
        as_of_date=snapshot.as_of_date,
        regime=regime,
        score=bounded_score,
        indicators=indicators,
        reasons=reasons,
    )


def _regime_from_score(score: int, vix: float | None) -> str:
    if score <= 25 or (vix is not None and vix >= 35):
        return "risk_off"
    if score <= 45 or (vix is not None and vix >= 25):
        return "cautious"
    if score >= 65:
        return "risk_on"
    return "neutral"
