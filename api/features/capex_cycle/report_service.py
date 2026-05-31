from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Iterable, Mapping, Sequence

from api.features.capex_cycle.report_schemas import (
    CapexAnchorClassification,
    CapexAnchorClassificationItem,
    CapexCycleReportResponse,
    CapexReportVersions,
    SourceHealthItem,
)
from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
    ReasonItem,
    WarningItem,
)
from api.features.capex_cycle.service import CapexCycleService


SourceHealthProvider = Callable[[date], Sequence[SourceHealthItem]]


@dataclass
class CapexCycleReportService:
    feature_service: Any = field(default_factory=CapexCycleService)
    repository: Any | None = None
    source_health_provider: SourceHealthProvider | None = None
    default_asset_ids: tuple[str, ...] = ("sample_ai_infra",)

    def get_report(self, *, as_of_date: date | None = None, asset_ids: Sequence[str] | None = None) -> CapexCycleReportResponse:
        decision_date = as_of_date or date.today()
        requested_assets = tuple(asset_ids or self.default_asset_ids)
        report_reasons = [ReasonItem(code="CAPEX_REPORT_ASSEMBLED", category="report")]
        report_warnings: list[WarningItem] = []

        ai_score, bio_scores = self._scores(decision_date, report_warnings, report_reasons)
        scenario = self._scenario(decision_date, report_warnings, report_reasons)
        valuations = [
            self._valuation(asset_id, decision_date, report_warnings, report_reasons)
            for asset_id in requested_assets
        ]
        source_health = self._source_health(decision_date, report_warnings, report_reasons)
        warnings = _aggregate_warnings(report_warnings, [ai_score], bio_scores, [scenario], valuations, source_health)
        reasons = _aggregate_reasons(report_reasons, [ai_score], bio_scores, [scenario], valuations, source_health)

        return CapexCycleReportResponse(
            as_of_date=decision_date,
            data_snapshot_id=self._data_snapshot_id(decision_date),
            source_health=list(source_health),
            ai_capex_score=ai_score,
            bio_bottleneck_scores=list(bio_scores),
            scenario_distribution=scenario,
            valuation_views=valuations,
            anchor_classifications=_classifications(bio_scores),
            warnings=warnings,
            reason_codes=reasons,
            versions=_versions(ai_score, bio_scores, scenario, valuations),
        )

    def _scores(
        self,
        decision_date: date,
        report_warnings: list[WarningItem],
        report_reasons: list[ReasonItem],
    ) -> tuple[CapexCycleScoreResponse, list[BioCapexBottleneckScoreResponse]]:
        try:
            scores = list(self.feature_service.get_scores(as_of_date=decision_date))
        except Exception as exc:
            report_warnings.append(_section_warning("scores", exc))
            report_reasons.append(ReasonItem(code="CAPEX_REPORT_SECTION_UNAVAILABLE", category="report", detail="scores"))
            return _fallback_ai_score(decision_date), []

        ai_score = next((score for score in scores if isinstance(score, CapexCycleScoreResponse)), None)
        bio_scores = [score for score in scores if isinstance(score, BioCapexBottleneckScoreResponse)]
        if ai_score is None:
            report_warnings.append(_section_warning("ai_capex_score", "missing score response"))
            ai_score = _fallback_ai_score(decision_date)
        return ai_score, bio_scores

    def _scenario(
        self,
        decision_date: date,
        report_warnings: list[WarningItem],
        report_reasons: list[ReasonItem],
    ) -> CapexScenarioResponse:
        try:
            return self.feature_service.get_scenario(as_of_date=decision_date)
        except Exception as exc:
            report_warnings.append(_section_warning("scenario", exc))
            report_reasons.append(ReasonItem(code="CAPEX_REPORT_SECTION_UNAVAILABLE", category="report", detail="scenario"))
            return _fallback_scenario(decision_date)

    def _valuation(
        self,
        asset_id: str,
        decision_date: date,
        report_warnings: list[WarningItem],
        report_reasons: list[ReasonItem],
    ) -> CapexValuationResponse:
        try:
            return self.feature_service.get_valuation(asset_id=asset_id, as_of_date=decision_date)
        except Exception as exc:
            report_warnings.append(_section_warning(f"valuation:{asset_id}", exc))
            report_reasons.append(ReasonItem(code="CAPEX_REPORT_SECTION_UNAVAILABLE", category="report", detail=f"valuation:{asset_id}"))
            return _fallback_valuation(asset_id, decision_date)

    def _source_health(
        self,
        decision_date: date,
        report_warnings: list[WarningItem],
        report_reasons: list[ReasonItem],
    ) -> list[SourceHealthItem]:
        if self.source_health_provider is None:
            report_warnings.append(
                WarningItem(
                    code="SOURCE_HEALTH_UNAVAILABLE",
                    severity="WARNING",
                    source="report",
                    message="source health provider is not configured",
                )
            )
            report_reasons.append(ReasonItem(code="SOURCE_HEALTH_CONSERVATIVE_EMPTY", category="report"))
            return []
        try:
            return list(self.source_health_provider(decision_date))
        except Exception as exc:
            report_warnings.append(_section_warning("source_health", exc))
            report_reasons.append(ReasonItem(code="CAPEX_REPORT_SECTION_UNAVAILABLE", category="report", detail="source_health"))
            return []

    def _data_snapshot_id(self, decision_date: date) -> str:
        if self.repository is None or not hasattr(self.repository, "get_universe_metadata"):
            return "unavailable"
        metadata = self.repository.get_universe_metadata(as_of_date=decision_date)
        if not isinstance(metadata, Mapping):
            return "unavailable"
        return str(metadata.get("data_snapshot_id") or metadata.get("snapshot_id") or metadata.get("universe_id") or "unavailable")


def _fallback_ai_score(as_of_date: date) -> CapexCycleScoreResponse:
    warning = _unavailable_warning("ai_capex_score")
    return CapexCycleScoreResponse(
        feature_id="feature:ai_capex_cycle",
        entity_id="ai_infrastructure",
        score=0.5,
        confidence=0.0,
        data_quality=0.0,
        as_of_date=as_of_date,
        parameter_version="unavailable",
        model_version="unavailable",
        reason_codes=[ReasonItem(code="CAPEX_REPORT_SECTION_UNAVAILABLE", category="report", detail="ai_capex_score")],
        warnings=[warning],
    )


def _fallback_scenario(as_of_date: date) -> CapexScenarioResponse:
    warning = _unavailable_warning("scenario")
    return CapexScenarioResponse(
        scenario_id="capex_scenario_distribution",
        score=0.0,
        confidence=0.0,
        data_quality=0.0,
        scenario_distribution={"REVIEW_REQUIRED": 1.0},
        dominant_scenario="REVIEW_REQUIRED",
        as_of_date=as_of_date,
        parameter_version="unavailable",
        model_version="unavailable",
        reason_codes=[ReasonItem(code="CAPEX_REPORT_SECTION_UNAVAILABLE", category="report", detail="scenario")],
        warnings=[warning],
    )


def _fallback_valuation(asset_id: str, as_of_date: date) -> CapexValuationResponse:
    warning = _unavailable_warning(f"valuation:{asset_id}")
    return CapexValuationResponse(
        asset_id=asset_id,
        score=0.5,
        confidence=0.0,
        data_quality=0.0,
        fair_value=None,
        current_price=None,
        fair_value_ratio=None,
        target_per=None,
        as_of_date=as_of_date,
        parameter_version="unavailable",
        model_version="unavailable",
        reason_codes=[ReasonItem(code="CAPEX_REPORT_SECTION_UNAVAILABLE", category="report", detail=f"valuation:{asset_id}")],
        warnings=[warning],
    )


def _section_warning(section: str, exc: Exception | str) -> WarningItem:
    return WarningItem(
        code="CAPEX_REPORT_SECTION_UNAVAILABLE",
        severity="WARNING",
        source="report",
        message=f"{section}: {exc}",
    )


def _unavailable_warning(section: str) -> WarningItem:
    return WarningItem(
        code="CAPEX_REPORT_SECTION_UNAVAILABLE",
        severity="WARNING",
        source="report",
        message=f"{section} unavailable; REVIEW_REQUIRED",
    )


def _classifications(scores: Iterable[BioCapexBottleneckScoreResponse]) -> list[CapexAnchorClassificationItem]:
    items: list[CapexAnchorClassificationItem] = []
    for score in scores:
        classification = (
            CapexAnchorClassification.RESEARCH_CORE_ANCHOR
            if score.core_anchor_allowed
            else CapexAnchorClassification.OBSERVATION_ONLY
        )
        items.append(
            CapexAnchorClassificationItem(
                asset_id=score.asset_id,
                classification=classification,
                confidence=score.confidence,
                reason_codes=score.reason_codes,
                warnings=score.warnings,
            )
        )
    return items


def _versions(
    ai_score: CapexCycleScoreResponse,
    bio_scores: Sequence[BioCapexBottleneckScoreResponse],
    scenario: CapexScenarioResponse,
    valuations: Sequence[CapexValuationResponse],
) -> CapexReportVersions:
    score_versions = {
        "ai_capex_score": ai_score.model_version,
        "scenario_distribution": scenario.model_version,
    }
    parameter_versions = {
        "ai_capex_score": ai_score.parameter_version,
        "scenario_distribution": scenario.parameter_version,
    }
    for score in bio_scores:
        score_versions[f"bio_bottleneck:{score.asset_id}"] = score.model_version
        parameter_versions[f"bio_bottleneck:{score.asset_id}"] = score.parameter_version
    for valuation in valuations:
        score_versions[f"valuation:{valuation.asset_id}"] = valuation.model_version
        parameter_versions[f"valuation:{valuation.asset_id}"] = valuation.parameter_version
    return CapexReportVersions(
        report_schema_version="capex_report_v1",
        data_snapshot_version="capex_raw_snapshot_v1",
        score_model_versions=score_versions,
        parameter_versions=parameter_versions,
    )


def _aggregate_warnings(
    initial: Sequence[WarningItem],
    *sections: Sequence[Any],
) -> list[WarningItem]:
    warnings = list(initial)
    for section in sections:
        for item in section:
            warnings.extend(getattr(item, "warnings", []) or [])
    return warnings


def _aggregate_reasons(
    initial: Sequence[ReasonItem],
    *sections: Sequence[Any],
) -> list[ReasonItem]:
    reasons = list(initial)
    for section in sections:
        for item in section:
            reasons.extend(getattr(item, "reason_codes", []) or [])
    return reasons
