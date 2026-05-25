from __future__ import annotations

import sqlite3
from datetime import date
from statistics import mean

from api.bottleneck_data_service import BottleneckIndicatorItem, get_bottleneck_snapshot
from api.strategy_config import load_sector_taxonomy
from api.trade_data_service import TradeSeriesItem, get_trade_snapshot

from .types import SectorBottleneckScore


class BottleneckSectorEngine:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def score(
        self,
        as_of_date: date,
        *,
        lookback_months: int = 60,
    ) -> list[SectorBottleneckScore]:
        taxonomy = load_sector_taxonomy()
        trade_snapshot = get_trade_snapshot(
            self.conn,
            as_of_date,
            lookback_months=lookback_months,
        )
        bottleneck_snapshot = get_bottleneck_snapshot(
            self.conn,
            as_of_date,
            lookback_months=lookback_months,
        )
        indicators_by_sector: dict[str, list[BottleneckIndicatorItem]] = {}
        for item in bottleneck_snapshot.indicators:
            indicators_by_sector.setdefault(item.sector_code, []).append(item)

        scores = []
        for sector_code, sector in taxonomy.items():
            trade_score, trade_reasons = _score_trade_items(
                trade_snapshot.items,
                set(sector.get("trade_items") or []),
            )
            sector_indicators = indicators_by_sector.get(sector_code, [])
            demand_score = _score_layer(sector_indicators, "demand")
            supply_score = _score_layer(sector_indicators, "supply")
            relative_score = _score_relative_strength(sector_indicators)
            total = (
                trade_score * 0.40
                + demand_score * 0.20
                + supply_score * 0.15
                + relative_score * 0.25
            )
            indicator_reasons = _indicator_reasons(sector_indicators)
            scores.append(SectorBottleneckScore(
                sector_code=sector_code,
                total_score=round(total, 2),
                trade_score=round(trade_score, 2),
                demand_score=round(demand_score, 2),
                supply_score=round(supply_score, 2),
                relative_strength_score=round(relative_score, 2),
                regime=_sector_regime(total),
                reasons=[*trade_reasons, *indicator_reasons] or ["No bottleneck signal available"],
            ))
        return scores


def _score_trade_items(
    items: list[TradeSeriesItem],
    item_codes: set[str],
) -> tuple[float, list[str]]:
    if not item_codes:
        return 50.0, []
    latest_by_item: dict[str, TradeSeriesItem] = {}
    for item in items:
        if item.item_code not in item_codes or item.yoy is None:
            continue
        previous = latest_by_item.get(item.item_code)
        if not previous or item.release_date >= previous.release_date:
            latest_by_item[item.item_code] = item
    if not latest_by_item:
        return 50.0, []

    yoy_values = [item.yoy for item in latest_by_item.values() if item.yoy is not None]
    score = _clamp(50.0 + mean(yoy_values), 0.0, 100.0)
    reasons = [
        f"{item.item_code} trade YoY {item.yoy:+.1f}%"
        for item in latest_by_item.values()
        if item.yoy is not None
    ]
    return score, reasons


def _score_layer(items: list[BottleneckIndicatorItem], layer: str) -> float:
    values = [
        item.value
        for item in _latest_indicators(items, layer=layer).values()
        if item.value is not None
    ]
    if not values:
        return 50.0
    return _clamp(mean(values), 0.0, 100.0)


def _score_relative_strength(items: list[BottleneckIndicatorItem]) -> float:
    latest = _latest_indicators(items, layer="relative_strength")
    if not latest:
        latest = {
            key: item
            for key, item in _latest_indicators(items).items()
            if key.upper().startswith("RS_")
        }
    values = [item.value for item in latest.values() if item.value is not None]
    if not values:
        return 50.0
    return _clamp(mean(values), 0.0, 100.0)


def _latest_indicators(
    items: list[BottleneckIndicatorItem],
    *,
    layer: str | None = None,
) -> dict[str, BottleneckIndicatorItem]:
    result: dict[str, BottleneckIndicatorItem] = {}
    for item in items:
        if layer and (item.layer or "").lower() != layer:
            continue
        previous = result.get(item.indicator_key)
        if not previous or item.release_date >= previous.release_date:
            result[item.indicator_key] = item
    return result


def _indicator_reasons(items: list[BottleneckIndicatorItem]) -> list[str]:
    reasons = []
    for item in _latest_indicators(items).values():
        if item.value is None:
            continue
        reasons.append(f"{item.indicator_key} {item.value:.1f}")
    return reasons


def _sector_regime(score: float) -> str:
    if score >= 70:
        return "active"
    if score >= 60:
        return "emerging"
    if score <= 40:
        return "weak"
    return "inactive"


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
