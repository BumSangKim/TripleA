import inspect
from datetime import UTC, date, datetime

from api.plugin_boundary.contracts import FeatureValue, PluginSignal
from api.plugin_boundary.input_resolver import FeatureInputResolver, FeatureSpec
from api.plugin_boundary.reference_features import PriceMomentumFeatureCalculator
import api.plugin_boundary.reference_features as reference_features_module
from api.plugin_boundary.reference_plugins import MockPricePlugin, MockSentimentPlugin
from api.plugin_boundary.registry import PluginRegistration, PluginRegistry


NOW = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)


def _price_rows():
    return [
        {"date": "2026-03-01", "close": "100"},
        {"date": "2026-05-27", "close": "112"},
    ]


def test_mock_price_plugin_creates_plugin_dataset():
    dataset = MockPricePlugin().get_dataset(
        entity_id="KRX_360750",
        rows=_price_rows(),
        as_of_date=date(2026, 5, 27),
        available_at=NOW,
        retrieved_at=NOW,
    )

    assert dataset.dataset_type == "market_price_daily"
    assert dataset.plugin_id == "mock_price_plugin"
    assert dataset.quality_score == 1.0


def test_resolver_passes_market_price_daily_dataset_to_calculator():
    dataset = MockPricePlugin().get_dataset(
        entity_id="KRX_360750",
        rows=_price_rows(),
        as_of_date=date(2026, 5, 27),
        available_at=NOW,
        retrieved_at=NOW,
    )
    registry = PluginRegistry()
    registry.register(PluginRegistration("mock_price_plugin", "mock", ("market_price_daily",), priority=1))
    spec = FeatureSpec(
        feature_id="market.price_momentum_3m",
        mode="reusable_calculator",
        entity_type="asset",
        required_dataset_types=("market_price_daily",),
        calculator="price_momentum_reference",
    )

    resolved = FeatureInputResolver(registry, [dataset]).resolve(spec, entity_id="KRX_360750", decision_time=NOW)
    feature = PriceMomentumFeatureCalculator().calculate(
        resolved.datasets_by_type["market_price_daily"],
        entity_id="KRX_360750",
        as_of_date=date(2026, 5, 27),
    )

    assert isinstance(feature, FeatureValue)
    assert feature.feature_id == "market.price_momentum_3m"
    assert feature.feature_value == 0.12
    assert feature.source_dataset_ids == [dataset.dataset_id]


def test_price_momentum_calculator_does_not_import_plugin_classes():
    source = inspect.getsource(reference_features_module)

    assert "MockPricePlugin" not in source
    assert "KISPricePlugin" not in source
    assert "reference_plugins" not in source


def test_mock_sentiment_plugin_creates_plugin_signal():
    signal = MockSentimentPlugin().get_signal(
        entity_type="asset",
        entity_id="KRX_360750",
        as_of_date=date(2026, 5, 27),
        available_at=NOW,
        retrieved_at=NOW,
    )

    assert isinstance(signal, PluginSignal)
    assert not isinstance(signal, FeatureValue)
    assert signal.source_native is True
    assert signal.signal_id == "plugin_signal:news_sentiment:KRX_360750"
