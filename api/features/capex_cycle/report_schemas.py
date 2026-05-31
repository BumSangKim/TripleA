from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from api.features.capex_cycle.schemas import (
    BioCapexBottleneckScoreResponse,
    CapexCycleScoreResponse,
    CapexScenarioResponse,
    CapexValuationResponse,
    ReasonItem,
    WarningItem,
)


class CapexAnchorClassification(StrEnum):
    RESEARCH_CORE_ANCHOR = "RESEARCH_CORE_ANCHOR"
    RESEARCH_SUPPORTING_EXPOSURE = "RESEARCH_SUPPORTING_EXPOSURE"
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class SourceHealthItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    status: str
    quality_score: float = Field(ge=0.0, le=1.0)
    last_available_at: Optional[datetime] = None
    warnings: List[WarningItem]
    reason_codes: List[ReasonItem]


class CapexAnchorClassificationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    classification: CapexAnchorClassification
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: List[ReasonItem]
    warnings: List[WarningItem]


class CapexReportVersions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_schema_version: str
    data_snapshot_version: str
    score_model_versions: Dict[str, str]
    parameter_versions: Dict[str, str]


class CapexCycleReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: date
    data_snapshot_id: str
    source_health: List[SourceHealthItem]
    ai_capex_score: CapexCycleScoreResponse
    bio_bottleneck_scores: List[BioCapexBottleneckScoreResponse]
    scenario_distribution: CapexScenarioResponse
    valuation_views: List[CapexValuationResponse]
    anchor_classifications: List[CapexAnchorClassificationItem] = Field(default_factory=list)
    warnings: List[WarningItem]
    reason_codes: List[ReasonItem]
    versions: CapexReportVersions
