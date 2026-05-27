from datetime import UTC, datetime

import pytest

from api.plugin_boundary.contracts import (
    PluginBoundaryContractError,
    PluginHealthStatus,
    PluginQualityScore,
    PluginRunMetadata,
)


NOW = datetime(2026, 5, 27, 9, 0, tzinfo=UTC)


def _quality(**overrides):
    data = {
        "plugin_id": "mock_price_plugin",
        "dataset_id": "ds-1",
        "dataset_type": "market_price_daily",
        "quality_score": 0.9,
        "missing_ratio": 0.0,
        "freshness_score": 0.8,
        "schema_valid": True,
        "is_stale": False,
        "fallback_used": False,
        "source_priority": 1,
        "measured_at": NOW,
    }
    data.update(overrides)
    return PluginQualityScore(**data)


def _health(**overrides):
    data = {
        "plugin_id": "mock_price_plugin",
        "status": "OK",
        "last_success_at": NOW,
        "last_failure_at": None,
        "error_code": None,
        "error_message": None,
        "latency_ms": 12,
        "checked_at": NOW,
    }
    data.update(overrides)
    return PluginHealthStatus(**data)


def test_valid_plugin_quality_score_can_be_created():
    quality = _quality(reason_codes=["PLUGIN_DATA_VALID"], warnings=[])

    assert quality.quality_score == 0.9
    assert quality.fallback_used is False
    assert quality.reason_codes == ["PLUGIN_DATA_VALID"]


def test_plugin_quality_score_range_is_validated():
    with pytest.raises(PluginBoundaryContractError, match="quality_score"):
        _quality(quality_score=-0.1)


def test_freshness_score_range_is_validated():
    with pytest.raises(PluginBoundaryContractError, match="freshness_score"):
        _quality(freshness_score=1.2)


def test_fallback_used_metadata_is_preserved():
    quality = _quality(
        quality_score=0.4,
        fallback_used=True,
        reason_codes=["PLUGIN_FALLBACK_USED"],
        warnings=["PLUGIN_DATA_MISSING"],
    )

    assert quality.fallback_used is True
    assert "PLUGIN_FALLBACK_USED" in quality.reason_codes
    assert "PLUGIN_DATA_MISSING" in quality.warnings


def test_health_status_enum_is_validated():
    with pytest.raises(PluginBoundaryContractError, match="status"):
        _health(status="BUY")


def test_plugin_failure_status_requires_error_code():
    with pytest.raises(PluginBoundaryContractError, match="error_code"):
        _health(status="FAILED", error_code=None)

    failed = _health(status="FAILED", last_failure_at=NOW, error_code="PLUGIN_PROVIDER_ERROR")
    assert failed.status == "FAILED"
    assert failed.error_code == "PLUGIN_PROVIDER_ERROR"


def test_plugin_run_metadata_links_quality_and_health():
    health = _health()
    quality = _quality()

    run = PluginRunMetadata(
        plugin_id="mock_price_plugin",
        run_id="run-1",
        started_at=NOW,
        finished_at=NOW,
        status="OK",
        health=health,
        quality=quality,
    )

    assert run.health is health
    assert run.quality is quality


def test_plugin_run_metadata_rejects_mismatched_plugin_ids():
    with pytest.raises(PluginBoundaryContractError, match="health.plugin_id"):
        PluginRunMetadata(
            plugin_id="mock_price_plugin",
            run_id="run-1",
            started_at=NOW,
            finished_at=NOW,
            status="OK",
            health=_health(plugin_id="other_plugin"),
        )
