from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


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
