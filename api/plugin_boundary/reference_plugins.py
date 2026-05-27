from __future__ import annotations

from datetime import date, datetime

from api.plugin_boundary.contracts import PluginDataset, PluginQualityScore, PluginSignal


class MockPricePlugin:
    plugin_id = "mock_price_plugin"
    provider = "mock"

    def get_dataset(
        self,
        *,
        entity_id: str,
        rows: list[dict],
        as_of_date: date,
        available_at: datetime,
        retrieved_at: datetime,
    ) -> PluginDataset:
        quality = self.get_quality(as_of_date=as_of_date, measured_at=retrieved_at)
        return PluginDataset(
            dataset_id=f"mock_price:{entity_id}:{as_of_date.isoformat()}",
            dataset_type="market_price_daily",
            plugin_id=self.plugin_id,
            provider=self.provider,
            source="mock_price_reference",
            entity_type="asset",
            entity_id=entity_id,
            data=rows,
            schema_version="plugin_dataset_v1",
            as_of_date=as_of_date,
            available_at=available_at,
            retrieved_at=retrieved_at,
            quality_score=quality.quality_score,
            missing_ratio=quality.missing_ratio,
            is_stale=quality.is_stale,
            reason_codes=quality.reason_codes,
        )

    def get_quality(self, *, as_of_date: date, measured_at: datetime) -> PluginQualityScore:
        return PluginQualityScore(
            plugin_id=self.plugin_id,
            dataset_id=None,
            dataset_type="market_price_daily",
            quality_score=1.0,
            missing_ratio=0.0,
            freshness_score=1.0,
            schema_valid=True,
            is_stale=False,
            fallback_used=False,
            source_priority=1,
            reason_codes=["PLUGIN_DATA_VALID"],
            warnings=[],
            measured_at=measured_at,
        )


class MockSentimentPlugin:
    plugin_id = "mock_sentiment_plugin"
    provider = "mock"

    def get_signal(
        self,
        *,
        entity_type: str,
        entity_id: str,
        as_of_date: date,
        available_at: datetime,
        retrieved_at: datetime,
    ) -> PluginSignal:
        return PluginSignal(
            signal_id=f"plugin_signal:news_sentiment:{entity_id}",
            plugin_id=self.plugin_id,
            provider=self.provider,
            source="mock_sentiment_reference",
            entity_type=entity_type,
            entity_id=entity_id,
            signal_value="positive",
            signal_unit="category",
            signal_direction="risk_up",
            source_native=True,
            calculation_method="provider_native_sentiment",
            plugin_version="mock_sentiment_v1",
            signal_version="plugin_signal_v1",
            as_of_date=as_of_date,
            available_at=available_at,
            retrieved_at=retrieved_at,
            quality_score=0.8,
            source_dataset_ids=[],
            reason_codes=["PLUGIN_NATIVE_SIGNAL"],
            warnings=[],
            metadata={"usage_reason": "sentiment model output is provider-native"},
        )
