from datetime import date

import pytest

from api.backtest_foundation import (
    BacktestFoundationError,
    BacktestMetricCalculator,
    BacktestRunner,
    BpsTransactionCostModel,
    HistoricalSnapshot,
    InMemoryHistoricalDataLoader,
    PortfolioState,
    SimulatedTrade,
    SimulationClock,
    SimulationConfig,
    StrategyDecisionOutput,
    apply_simulated_trade,
)
from api.strategy.audit_layer import (
    AuditWarning,
    BacktestReportGenerator,
    DecisionLog,
    DecisionLogEntry,
    DecisionTrace,
    ExplanationService,
    aggregate_warnings,
    validate_reason_catalog,
)
from api.strategy.order_candidates import (
    CandidateContext,
    build_user_review_output,
    generate_order_candidates_from_rebalance,
    validate_candidate_inputs,
)
from api.strategy.phase_engines import (
    AllocationInput,
    MacroRegimeDistributionEngine,
    MacroRegimeInput,
    RebalanceInput,
    RebalancingIntensityEngine,
    RiskBudgetInput,
    RiskBudgetScoringEngine,
    ScoreBasedAllocationEngine,
    SectorScoreInput,
    SectorScoringEngine,
    TargetRange,
    load_sector_definitions,
)


def test_simulation_clock_dates_are_deterministic_and_invalid_order_rejected():
    config = SimulationConfig(date(2026, 1, 1), date(2026, 3, 1), "monthly", 1000)
    assert [item.as_of_date for item in SimulationClock(config).dates()] == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
    with pytest.raises(BacktestFoundationError):
        SimulationConfig(date(2026, 2, 1), date(2026, 1, 1))


def test_historical_snapshot_rejects_future_data():
    snapshot = HistoricalSnapshot(date(2026, 5, 28), "future", {})
    with pytest.raises(BacktestFoundationError, match="future"):
        snapshot.assert_available_for(date(2026, 5, 27))


def test_portfolio_state_and_cost_hooks_block_insufficient_cash():
    state = PortfolioState(100)
    trade = SimulatedTrade("SMH", "BUY", 2, 60)
    blocked = apply_simulated_trade(state, trade, BpsTransactionCostModel(10))
    assert "INSUFFICIENT_CASH_BLOCKED_RISK_INCREASE" in blocked.warnings
    bought = apply_simulated_trade(state, SimulatedTrade("SMH", "BUY", 1, 50), BpsTransactionCostModel(10))
    assert bought.cash < 50
    sold = apply_simulated_trade(bought, SimulatedTrade("SMH", "SELL", 1, 55), BpsTransactionCostModel(0))
    assert sold.cash > bought.cash


def test_metric_calculator_known_curve_and_flat_curve_warning():
    metrics, warnings = BacktestMetricCalculator().calculate([(date(2026, 1, 1), 100), (date(2026, 1, 2), 90), (date(2026, 1, 3), 110)])
    flat, flat_warnings = BacktestMetricCalculator().calculate([(date(2026, 1, 1), 100), (date(2026, 1, 2), 100)])
    assert metrics["total_return"] == pytest.approx(0.1)
    assert metrics["mdd"] == pytest.approx(-0.1)
    assert flat["annualized_volatility"] == 0
    assert "SHARPE_UNAVAILABLE_ZERO_VOLATILITY" in flat_warnings
    assert warnings == []


class HoldStrategy:
    def decide(self, decision_input):
        return StrategyDecisionOutput(decision_input.as_of_date, decision_input.data_snapshot_id, "HOLD")


class BuyStrategy:
    def decide(self, decision_input):
        price = decision_input.snapshot.data["prices"]["SMH"]
        return StrategyDecisionOutput(decision_input.as_of_date, decision_input.data_snapshot_id, "BUY_CANDIDATE", [SimulatedTrade("SMH", "BUY", 1, price)])


def test_backtest_runner_is_reproducible_and_loader_is_leakage_safe():
    snapshots = [HistoricalSnapshot(date(2026, 1, 1), "snap-1", {"prices": {"SMH": 10}})]
    config = SimulationConfig(date(2026, 1, 1), date(2026, 2, 1), "monthly", 1000)
    runner = BacktestRunner(InMemoryHistoricalDataLoader(snapshots), BuyStrategy())
    first = runner.run(config)
    second = runner.run(config)
    assert first.equity_curve == second.equity_curve
    assert first.decisions[0].simulated_trades[0].price == 10


def test_macro_regime_distribution_is_continuous_and_not_fixed_weight_mapping():
    result = MacroRegimeDistributionEngine().evaluate(
        MacroRegimeInput(date(2026, 5, 27), {"growth": 0.8, "inflation": 0.2, "credit": 0.4, "volatility": 0.3})
    )
    assert sum(result.regime_distribution.values()) == pytest.approx(1.0)
    assert result.dominant_regime_explanation_only is True
    assert not hasattr(result, "target_weights")


def test_macro_all_missing_returns_conservative_fallback():
    result = MacroRegimeDistributionEngine().evaluate(MacroRegimeInput(date(2026, 5, 27), {"growth": None}))
    assert "REVIEW_REQUIRED" in result.warnings
    assert result.confidence == 0


def test_sector_config_components_ranking_and_no_order_output():
    definitions = load_sector_definitions()
    engine = SectorScoringEngine(definitions)
    semi = engine.score_sector(SectorScoreInput(date(2026, 5, 27), "semiconductors", {"risk_on_growth": 0.6}, {"industry_momentum": 0.8, "earnings_trend": None, "price_momentum": 0.7, "valuation": 0.4, "supply_demand": 0.6, "risk_penalty": 0.2}, 0.8, 0.8))
    bond = engine.score_sector(SectorScoreInput(date(2026, 5, 27), "defensive_bonds", {"volatility_stress": 0.6}, {"industry_momentum": 0.4, "price_momentum": 0.4, "valuation": 0.6, "supply_demand": 0.5, "risk_penalty": 0.1}, 0.9, 0.9))
    ranked = engine.rank([semi, bond])
    assert ranked[0].rank == 1
    assert "MISSING_SECTOR_COMPONENT:earnings_trend" in semi.warnings
    assert not hasattr(semi, "order_candidates")


def test_risk_budget_separates_account_and_portfolio_limits():
    result = RiskBudgetScoringEngine().evaluate(
        RiskBudgetInput(date(2026, 5, 27), "acct-1", "IRP", {"SMH": 0.8, "TLT": 0.2}, {"SMH"}, {"SMH": 0.9}, {"SMH": 0.8}, -0.1)
    )
    assert result.account.blocked is True
    assert "ACCOUNT_RISK_LIMIT_BREACH" in result.reason_codes
    assert result.portfolio.risk_budget_score < 1


def test_missing_account_state_blocks_risk_increase():
    result = RiskBudgetScoringEngine().evaluate(RiskBudgetInput(date(2026, 5, 27), None, None, {"SMH": 0.1}, {"SMH"}))
    assert result.risk_increase_allowed is False
    assert "MISSING_ACCOUNT_STATE" in result.warnings


def test_allocation_gradual_weight_calculation_and_constraint_block():
    engine = ScoreBasedAllocationEngine()
    target_range = TargetRange("SMH", 0.0, 0.1, 0.2, 0.03)
    result = engine.calculate(AllocationInput(date(2026, 5, 27), "SMH", target_range, 0.1, {"risk_on_growth": 0.6}, 0.9, 0.8, 0.9))
    blocked = engine.calculate(AllocationInput(date(2026, 5, 27), "SMH", target_range, 0.1, {"risk_on_growth": 0.6}, 0.9, 0.8, 0.9, True))
    assert 0.1 < result.current_target_weight <= 0.13
    assert blocked.current_target_weight == 0
    assert "HARD_CONSTRAINT_BLOCKED" in blocked.reason_codes


def test_allocation_normalizes_residual_to_cash():
    engine = ScoreBasedAllocationEngine()
    target_range = TargetRange("SMH", 0.0, 0.1, 0.2, 0.03)
    result = engine.calculate(AllocationInput(date(2026, 5, 27), "SMH", target_range, 0.1, {"risk_on_growth": 0.6}, 0.9, 0.8, 0.9))
    normalized = engine.normalize([result])
    assert sum(item.current_target_weight for item in normalized) == pytest.approx(1.0)
    assert any(item.asset_id == "CASH_KRW" for item in normalized)


def test_rebalancing_preserves_improving_overweight_winner_and_risk_override():
    engine = RebalancingIntensityEngine()
    winner = engine.evaluate(RebalanceInput(date(2026, 5, 27), "SMH", 0.25, 0.1, 0.0, 0.2, 0.1, 0.1, 0.0, 0.0))
    risk = engine.evaluate(RebalanceInput(date(2026, 5, 27), "SMH", 0.25, 0.1, 0.0, 0.2, 0.1, 0.9, 0.0, 0.0))
    falling = engine.evaluate(RebalanceInput(date(2026, 5, 27), "SMH", 0.25, 0.1, 0.0, 0.2, -0.1, 0.1, 0.0, 0.0))
    assert winner.action_candidate.action == "HOLD_OVERWEIGHT_WINNER"
    assert risk.action_candidate.action == "RISK_REDUCE_ONLY"
    assert falling.action_candidate.action == "PARTIAL_REDUCTION_CANDIDATE"


def test_decision_log_catalog_report_and_explanation_service():
    validate_reason_catalog()
    warning = AuditWarning("LOW_CONFIDENCE", "macro", "WARNING")
    higher = AuditWarning("LOW_CONFIDENCE", "macro", "ERROR")
    assert aggregate_warnings([warning], [higher])[0].severity == "ERROR"
    entry = DecisionLogEntry(
        "decision-1",
        date(2026, 5, 27),
        "snap-1",
        "p",
        "m",
        "BUY_CANDIDATE",
        0.4,
        DecisionTrace(target_weights={"SMH": 0.12}, current_weights={"SMH": 0.08}),
        ["SCORE_BASED_GRADUAL_TARGET"],
        [warning],
    )
    log = DecisionLog("log-1", [entry])
    explanation = ExplanationService(log).explain("decision-1")
    assert explanation.available is True
    assert "SCORE_BASED_GRADUAL_TARGET" in explanation.reason_codes
    report = BacktestReportGenerator().generate_json(type("Result", (), {"metrics": {"cagr": 0.1, "mdd": -0.1}, "warnings": [], "parameter_version": "p", "model_version": "m"})())
    assert "METRIC_UNAVAILABLE:sharpe" in report["warnings"]
    assert "decision-1" in log.to_json()


def test_order_candidate_generation_validation_and_review_output():
    rebalance = RebalancingIntensityEngine().evaluate(RebalanceInput(date(2026, 5, 27), "SMH", 0.02, 0.1, 0.08, 0.15, 0.1, 0.1, 1.0, 0.0))
    context = CandidateContext("12345678", 100000, {"SMH": 0.02}, {"SMH": 100}, "snap-1", account_eligible_assets={"SMH"})
    candidates = generate_order_candidates_from_rebalance([rebalance], context)
    assert candidates[0].validation.actionable is True
    assert candidates[0].non_executable is True
    assert candidates[0].to_review_dict()["account_label"] == "****5678"
    review = build_user_review_output(candidates, batch_id="batch-1", as_of_date=date(2026, 5, 27), generated_at="2026-05-27T00:00:00")
    assert review.batch.actionable_candidates
    assert review.batch.non_execution is True


def test_order_candidate_constraints_block_invalid_inputs():
    validation = validate_candidate_inputs(
        asset_id="SMH",
        side="BUY",
        amount=1000,
        price=None,
        context=CandidateContext("", 10, {}, {}, "snap-1", min_order_value=2000, prohibited_assets={"SMH"}),
    )
    assert validation.blocked is True
    assert "PROHIBITED_ASSET_BLOCKED" in validation.reason_codes
    assert "MISSING_PRICE_BLOCKS_RISK_INCREASE" in validation.warnings
