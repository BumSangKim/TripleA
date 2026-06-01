from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BacktestRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "TripleA Dynamic Backtest"
    startDate: str
    endDate: str
    initialCapital: float
    strategyMode: str = "triplea_dynamic"
    riskProfile: str = "balanced"
    universeId: str = "default_global"
    rebalanceFrequency: str = "monthly"
    baseCurrency: str = "KRW"
    feeBps: float = 5.0
    slippageBps: float = 5.0
    taxBps: float = 0.0
    dataLookbackYears: int = 5
    enableScoreflowTestbed: bool = False
    enableDecisionLogging: bool = False
    parameterSetId: Optional[str] = None
    optimizationRunId: Optional[str] = None
    initialSeedPolicy: str = "CURRENT"


class BacktestPoint(BaseModel):
    date: str
    value: float
    drawdown: float


class BacktestPosition(BaseModel):
    date: str
    assetCode: str
    quantity: float
    price: float
    fxRate: float
    marketValue: float
    weight: float


class BacktestTrade(BaseModel):
    date: str
    assetCode: str
    side: str
    quantity: float
    price: float
    fxRate: float
    grossAmount: float
    fee: float = 0
    slippage: float = 0
    tax: float = 0
    netAmount: float
    reason: Optional[str] = None


class BacktestDecision(BaseModel):
    date: str
    strategyMode: str
    riskProfile: Optional[str] = None
    universeId: Optional[str] = None
    macroRegime: Optional[str] = None
    macroScore: Optional[int] = None
    bucketWeights: Dict[str, float] = Field(default_factory=dict)
    finalWeights: Dict[str, float] = Field(default_factory=dict)
    bottleneckScores: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)


class BacktestRunResponse(BaseModel):
    ok: bool
    runId: int
    name: str
    startDate: str
    endDate: str
    initialCapital: float
    strategyMode: str = "triplea_dynamic"
    riskProfile: str = "balanced"
    universeId: str = "default_global"
    rebalanceFrequency: str
    baseCurrency: str = "KRW"
    feeBps: float = 0
    slippageBps: float = 0
    taxBps: float = 0
    dataLookbackYears: int = 5
    status: str
    totalReturn: float
    annualReturn: float
    maxDrawdown: float
    volatility: float
    points: List[BacktestPoint]
    positions: List[BacktestPosition] = Field(default_factory=list)
    trades: List[BacktestTrade] = Field(default_factory=list)
    decisions: List[BacktestDecision] = Field(default_factory=list)
    createdAt: Optional[str] = None


class SectorComponentScopePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["all", "single"]
    sectorId: Optional[str] = None

    @model_validator(mode="after")
    def validate_scope(self) -> "SectorComponentScopePayload":
        if self.mode == "all" and self.sectorId is not None:
            raise ValueError("all sector scope must not include sectorId")
        if self.mode == "single" and not (isinstance(self.sectorId, str) and self.sectorId.strip()):
            raise ValueError("single sector scope requires sectorId")
        if isinstance(self.sectorId, str):
            self.sectorId = self.sectorId.strip()
        return self


class SectorComponentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sectorScope: SectorComponentScopePayload


class SectorComponentComparisonRowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sectorId: str
    displayName: str
    portfolioId: str
    status: str
    totalReturn: Optional[float] = None
    maxDrawdown: Optional[float] = None
    volatility: Optional[float] = None
    hitRate: Optional[float] = None
    observationCount: int = 0
    warningCount: int = 0
    reasonCodes: List[str] = Field(default_factory=list)


class SectorComponentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    sectorScope: SectorComponentScopePayload
    semantics: str = "independent_enabled_sector_backtests"
    parameterVersion: str
    modelVersion: str
    dataSnapshotId: str
    status: str
    comparisonRows: List[SectorComponentComparisonRowResponse] = Field(default_factory=list)
    sectorResults: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    reasonCodes: List[str] = Field(default_factory=list)


class SectorComponentAllSectorOptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str
    sectorScope: SectorComponentScopePayload


class SectorComponentSectorOptionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str
    sectorId: str
    portfolioId: str
    enabled: bool
    assetCount: int
    assets: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    reasonCodes: List[str] = Field(default_factory=list)


class SectorComponentUiMetadataResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    parameterVersion: str
    modelVersion: str
    allSectorOption: SectorComponentAllSectorOptionResponse
    sectorOptions: List[SectorComponentSectorOptionResponse] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    reasonCodes: List[str] = Field(default_factory=list)
