from api.asset_universe_validator import validate_asset_universe_config


def _asset(asset_id="SPY", **overrides):
    asset = {
        "asset_id": asset_id,
        "symbol": asset_id,
        "name": f"{asset_id} Asset",
        "asset_class": "global_equity",
        "sector": None,
        "region": "US",
        "currency": "USD",
        "instrument_type": "ETF",
        "enabled": True,
        "role": "core",
        "risk_tier": "medium",
        "liquidity_tier": "high",
        "min_order_unit": 1,
        "data_requirements": ["price_daily"],
        "account_eligibility": {
            "taxable": {"eligible": True, "review_required": False, "restrictions": []},
            "isa": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
            "pension": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
            "irp": {"eligible": False, "review_required": True, "restrictions": ["not_reviewed"]},
        },
        "review_required": False,
        "notes": "Test asset",
    }
    asset.update(overrides)
    return asset


def _config(*assets):
    return {
        "universe_id": "test_universe",
        "version": "test.1",
        "description": "Test universe",
        "base_currency": "KRW",
        "assets": list(assets),
    }


def test_clean_universe_returns_valid():
    result = validate_asset_universe_config(_config(_asset("SPY"), _asset("CASH", role="cash", risk_tier="low")))

    assert result.is_valid is True
    assert result.errors == []
    assert result.active_asset_count == 2
    assert result.conservative_state is None


def test_duplicate_id_returns_blocking_error():
    result = validate_asset_universe_config(_config(_asset("SPY"), _asset("SPY")))

    assert result.is_valid is False
    assert any(issue.field == "asset_id" for issue in result.errors)
    assert result.conservative_state == "NO_ACTION"


def test_missing_required_field_returns_blocking_error():
    raw = _asset("SPY")
    raw.pop("currency")
    result = validate_asset_universe_config(_config(raw))

    assert result.is_valid is False
    assert any("currency" in issue.message for issue in result.errors)


def test_enabled_asset_without_data_requirements_returns_blocking_error():
    result = validate_asset_universe_config(_config(_asset("SPY", data_requirements=[])))

    assert result.is_valid is False
    assert any(issue.field == "data_requirements" for issue in result.errors)


def test_high_risk_satellite_without_notes_returns_warning_and_review():
    result = validate_asset_universe_config(
        _config(
            _asset(
                "SMH",
                role="satellite",
                risk_tier="very_high",
                sector="SEMICONDUCTOR",
                notes=None,
                review_required=True,
            )
        )
    )

    assert result.is_valid is True
    assert any(issue.field == "notes" for issue in result.warnings)
    assert "SMH" in result.review_required_assets


def test_disabled_asset_does_not_cause_tradability():
    result = validate_asset_universe_config(_config(_asset("WATCH", enabled=False, role="watchlist")))

    assert result.is_valid is True
    assert result.active_asset_count == 0


def test_disabled_asset_marked_tradable_is_blocking_error():
    result = validate_asset_universe_config(
        _config(_asset("WATCH", enabled=False, role="watchlist", eligible_for_order_candidate=True))
    )

    assert result.is_valid is False
    assert any(issue.field == "eligible_for_order_candidate" for issue in result.errors)
