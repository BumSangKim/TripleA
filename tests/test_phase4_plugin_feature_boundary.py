import inspect
import json
from dataclasses import fields
from datetime import UTC, date, datetime
from pathlib import Path

from api.plugin_boundary.contracts import FeatureValue, PluginQualityScore, PluginSignal
from api.plugin_boundary.input_resolver import FeatureInputResolver, FeatureSpec
from api.plugin_boundary.reference_features import PriceMomentumFeatureCalculator
import api.plugin_boundary.reference_features as reference_features_module
from api.plugin_boundary.reference_plugins import MockPricePlugin, MockSentimentPlugin
from api.plugin_boundary.registry import PluginRegistration, PluginRegistry


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "phase4_plugin_feature"
DECISION_TIME = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)


def _load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _registry():
    registry = PluginRegistry()
    registry.register(PluginRegistration("mock_price_plugin", "mock", ("market_price_daily",), priority=1))
    return registry


def _spec():
    return FeatureSpec(
        feature_id="market.price_momentum_3m",
        mode="reusable_calculator",
        entity_type="asset",
        required_dataset_types=("market_price_daily",),
        calculator="price_momentum_reference",
    )


def test_plugin_dataset_to_feature_value_flow_from_fixture():
    fixture = _load_fixture("mock_market_price_daily.json")
    dataset = MockPricePlugin().get_dataset(
        entity_id=fixture["entity_id"],
        rows=fixture["rows"],
        as_of_date=date(2026, 5, 27),
        available_at=DECISION_TIME,
        retrieved_at=DECISION_TIME,
    )

    resolved = FeatureInputResolver(_registry(), [dataset]).resolve(
        _spec(),
        entity_id=fixture["entity_id"],
        decision_time=DECISION_TIME,
    )
    feature = PriceMomentumFeatureCalculator().calculate(
        resolved.datasets_by_type["market_price_daily"],
        entity_id=fixture["entity_id"],
        as_of_date=date(2026, 5, 27),
    )

    assert isinstance(feature, FeatureValue)
    assert feature.feature_value == 0.12
    assert feature.source_dataset_ids == [dataset.dataset_id]


def test_plugin_quality_is_not_misclassified_as_investment_score():
    fixture = _load_fixture("mock_plugin_quality.json")
    quality = MockPricePlugin().get_quality(as_of_date=date(2026, 5, 27), measured_at=DECISION_TIME)

    assert isinstance(quality, PluginQualityScore)
    assert quality.plugin_id == fixture["plugin_id"]
    assert quality.quality_score == fixture["quality_score"]
    assert not hasattr(quality, "decision_score")
    assert not hasattr(quality, "buy_signal")


def test_plugin_signal_remains_separate_from_feature_value():
    fixture = _load_fixture("mock_plugin_signal.json")
    signal = MockSentimentPlugin().get_signal(
        entity_type="asset",
        entity_id="KRX_360750",
        as_of_date=date(2026, 5, 27),
        available_at=DECISION_TIME,
        retrieved_at=DECISION_TIME,
    )

    assert isinstance(signal, PluginSignal)
    assert not isinstance(signal, FeatureValue)
    assert signal.signal_id == fixture["signal_id"]
    assert signal.source_native is fixture["source_native"]


def test_reusable_calculator_depends_on_dataset_type_not_plugin_id():
    source = inspect.getsource(reference_features_module)
    calculator = PriceMomentumFeatureCalculator()

    assert calculator.required_dataset_types == ("market_price_daily",)
    assert "MockPricePlugin" not in source
    assert "reference_plugins" not in source


def test_future_available_dataset_is_excluded_by_resolver():
    fixture = _load_fixture("mock_future_available_dataset.json")
    dataset = MockPricePlugin().get_dataset(
        entity_id=fixture["entity_id"],
        rows=fixture["rows"],
        as_of_date=date(2026, 5, 28),
        available_at=datetime.fromisoformat(fixture["available_at"]),
        retrieved_at=datetime.fromisoformat(fixture["available_at"]),
    )

    resolved = FeatureInputResolver(_registry(), [dataset]).resolve(
        _spec(),
        entity_id=fixture["entity_id"],
        decision_time=DECISION_TIME,
    )

    assert resolved.datasets_by_type == {}
    assert resolved.fallback_used is True


def test_plugin_fallback_reason_code_is_recorded():
    resolved = FeatureInputResolver(_registry(), []).resolve(
        _spec(),
        entity_id="KRX_360750",
        decision_time=DECISION_TIME,
    )

    assert resolved.reason_codes == ["PLUGIN_DATASET_FALLBACK_USED"]
    assert resolved.warnings == ["PLUGIN_DATASET_UNAVAILABLE:market_price_daily"]


def test_no_feature_score_contract_or_field_exists():
    contract_names = {field.name for field in fields(FeatureValue)}

    assert "feature_score" not in contract_names
    assert "score" not in contract_names
    assert not hasattr(__import__("api.plugin_boundary.contracts", fromlist=["FeatureScore"]), "FeatureScore")


def test_hard_constraint_candidate_is_not_weakened_to_feature_value():
    fixture = _load_fixture("mock_broker_tradability.json")

    assert fixture["classification"] == "ConstraintInputCandidate"
    assert "hard constraint" in fixture["reason"]
