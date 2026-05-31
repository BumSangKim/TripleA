from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ReasonItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    category: str
    detail: Optional[str] = None


class WarningItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: str
    source: str
    message: str


class CapexCycleScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_id: str
    entity_id: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    data_quality: float = Field(ge=0.0, le=1.0)
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: List[ReasonItem] = Field(default_factory=list)
    warnings: List[WarningItem] = Field(default_factory=list)


class BioCapexBottleneckScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    data_quality: float = Field(ge=0.0, le=1.0)
    component_scores: Dict[str, float] = Field(default_factory=dict)
    core_anchor_allowed: bool
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: List[ReasonItem] = Field(default_factory=list)
    warnings: List[WarningItem] = Field(default_factory=list)


class CapexScenarioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    data_quality: float = Field(ge=0.0, le=1.0)
    scenario_distribution: Dict[str, float]
    dominant_scenario: str
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: List[ReasonItem] = Field(default_factory=list)
    warnings: List[WarningItem] = Field(default_factory=list)


class CapexValuationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    data_quality: float = Field(ge=0.0, le=1.0)
    fair_value: Optional[float] = None
    current_price: Optional[float] = None
    fair_value_ratio: Optional[float] = None
    target_per: Optional[float] = None
    as_of_date: date
    parameter_version: str
    model_version: str
    reason_codes: List[ReasonItem] = Field(default_factory=list)
    warnings: List[WarningItem] = Field(default_factory=list)
