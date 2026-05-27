from __future__ import annotations

from datetime import date
from decimal import Decimal

from api.plugin_boundary.contracts import FeatureValue, PluginBoundaryContractError, PluginDataset


class PriceMomentumFeatureCalculator:
    feature_id = "market.price_momentum_3m"
    required_dataset_types = ("market_price_daily",)
    feature_version = "price_momentum_reference_v1"

    def calculate(
        self,
        dataset: PluginDataset,
        *,
        entity_id: str,
        as_of_date: date,
        parameter_version: str | None = None,
    ) -> FeatureValue:
        if dataset.dataset_type != "market_price_daily":
            raise PluginBoundaryContractError("PriceMomentumFeatureCalculator requires market_price_daily")
        closes = [Decimal(str(row["close"])) for row in sorted(dataset.data, key=lambda row: row["date"])]
        if len(closes) < 2 or closes[0] <= 0:
            raise PluginBoundaryContractError("price momentum requires at least two positive close values")
        momentum = (closes[-1] - closes[0]) / closes[0]
        return FeatureValue(
            feature_id=self.feature_id,
            entity_type="asset",
            entity_id=entity_id,
            feature_value=float(momentum),
            unit="ratio",
            as_of_date=as_of_date,
            available_at=dataset.available_at,
            source_dataset_ids=[dataset.dataset_id],
            source_plugin_ids=[dataset.plugin_id],
            calculation_method="close_to_close_return",
            feature_version=self.feature_version,
            parameter_version=parameter_version,
            data_quality=dataset.quality_score,
            missing_ratio=dataset.missing_ratio,
            is_stale=dataset.is_stale,
            warnings=list(dataset.warnings),
            reason_codes=["FEATURE_VALUE_CREATED"],
            metadata={"required_dataset_types": list(self.required_dataset_types)},
        )
