from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from api.strategy.common_sector_scoring_engine import CommonSectorScore
from api.strategy.indicator_plugins.base import PluginScore
from api.strategy.score_contract import clamp_score, combine_reason_codes


@dataclass(frozen=True)
class AggregatedSectorScore:
    sector_code: str
    as_of_date: date
    common_score: float
    plugin_scores: dict[str, float]
    plugin_confidences: dict[str, float]
    total_score: float
    confidence: float
    data_quality: float
    reason_codes: list[str]
    model_version: str = "sector_score_aggregator_v1"
    parameter_version: str = "default"


def aggregate_sector_score(
    common: CommonSectorScore,
    plugin_scores: list[PluginScore],
    plugin_weights: dict[str, float] | None = None,
) -> AggregatedSectorScore:
    plugin_weights = plugin_weights or {}
    base_weight = 1.0
    weighted_sum = common.total_common_score * base_weight
    total_weight = base_weight
    for score in plugin_scores:
        weight = plugin_weights.get(score.plugin_name, 0.25)
        weighted_sum += score.score * weight * score.confidence
        total_weight += weight
    total = clamp_score(weighted_sum / total_weight)
    confidence_values = [common.confidence, *[score.confidence for score in plugin_scores]]
    data_quality_values = [common.data_quality, *[score.data_quality for score in plugin_scores]]
    return AggregatedSectorScore(
        sector_code=common.sector_code,
        as_of_date=common.as_of_date,
        common_score=common.total_common_score,
        plugin_scores={score.plugin_name: score.score for score in plugin_scores},
        plugin_confidences={score.plugin_name: score.confidence for score in plugin_scores},
        total_score=total,
        confidence=clamp_score(sum(confidence_values) / len(confidence_values)),
        data_quality=clamp_score(sum(data_quality_values) / len(data_quality_values)),
        reason_codes=combine_reason_codes(common.reason_codes, *[score.reason_codes for score in plugin_scores]),
    )
