import pytest

from api.data.source_registry import (
    DataSourceConfigError,
    executable_sources,
    load_data_sources,
    validate_data_source_config,
)


def test_data_sources_load_from_config():
    sources = load_data_sources()

    assert sources
    assert {source.source_type for source in sources}.issuperset({"market_price", "current_quote", "macro"})


def test_missing_required_field_fails_validation():
    with pytest.raises(DataSourceConfigError):
        validate_data_source_config(
            {
                "sources": [
                    {
                        "source_id": "broken",
                        "source_type": "macro",
                    }
                ]
            }
        )


def test_disabled_source_is_excluded_from_execution():
    sources = load_data_sources()

    executable = executable_sources(sources)

    assert "fred_disabled_without_secret" not in {source.source_id for source in executable}


def test_requires_secret_source_without_secret_is_not_executable():
    sources = load_data_sources()
    fred = [source for source in sources if source.source_id == "fred_disabled_without_secret"][0]
    enabled_secret_source = [fred.__class__(**{**fred.__dict__, "enabled": True})]

    assert executable_sources(enabled_secret_source, env={}) == []
