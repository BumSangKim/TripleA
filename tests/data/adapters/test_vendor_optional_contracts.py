from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from api.data.adapters.vendor_optional import (
    DisabledOptionalVendorAdapter,
    OptionalVendorAdapter,
    OptionalVendorMetadata,
    OptionalVendorNotConfiguredError,
)


def test_disabled_vendor_adapter_returns_not_configured_behavior() -> None:
    adapter = DisabledOptionalVendorAdapter()

    assert isinstance(adapter, OptionalVendorAdapter)
    assert adapter.metadata.enabled is False
    assert adapter.metadata.license_class == "licensed_vendor_required"
    with pytest.raises(OptionalVendorNotConfiguredError, match="REVIEW_REQUIRED"):
        adapter.fetch_time_series(
            metric_id="ai_infrastructure_capex_estimate",
            start=date(2024, 1, 1),
            end=date(2024, 12, 31),
        )


def test_disabled_vendor_company_metrics_do_not_return_synthetic_rows() -> None:
    adapter = DisabledOptionalVendorAdapter()

    with pytest.raises(OptionalVendorNotConfiguredError, match="not configured"):
        adapter.fetch_company_metrics(
            company_ids=("sample",),
            metric_ids=("segment_growth_estimate",),
        )


def test_optional_vendor_metadata_exposes_freshness_and_supported_metrics() -> None:
    metadata = OptionalVendorMetadata(
        vendor_id="licensed_vendor_x",
        license_class="paid_redistribution_restricted",
        enabled=False,
        freshness_days=7,
        supported_metric_ids=("company.book_to_bill",),
    )

    assert metadata.enabled is False
    assert metadata.freshness_days == 7
    assert metadata.supported_metric_ids == ("company.book_to_bill",)


def test_source_catalog_optional_vendors_are_disabled_by_default() -> None:
    data = yaml.safe_load(Path("config/data_sources/capex_cycle_sources.yaml").read_text())
    optional_groups = [group for group in data["source_groups"].values() if group.get("optional") is True]

    assert optional_groups
    assert all(group.get("enabled_by_default") is False for group in optional_groups)


def test_optional_vendor_contract_introduces_no_network_or_scraping_libraries() -> None:
    source = Path("api/data/adapters/vendor_optional.py").read_text()
    forbidden_terms = (
        "requests",
        "httpx",
        "urllib",
        "BeautifulSoup",
        "selenium",
        "playwright",
        "api.brokers",
        "api.features.orders",
        "api.strategy",
    )

    assert not any(term in source for term in forbidden_terms)
