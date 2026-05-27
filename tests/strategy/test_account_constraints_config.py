import pytest

from api.strategy.account_constraints.config import (
    AccountConstraintConfigError,
    load_account_constraint_config,
)


def _config(**overrides):
    raw = {
        "version": "test.1",
        "unknown_account_behavior": "REVIEW_REQUIRED",
        "accounts": {
            "taxable": _account("taxable", "aggressive_growth"),
            "isa": _account("isa", "tax_efficient_growth"),
            "pension": _account("pension", "long_term_growth", allow_satellite="limited"),
            "irp": _account("irp", "defensive_growth", allow_satellite=False, risky_asset_limit=0.70),
        },
    }
    raw.update(overrides)
    return raw


def _account(
    account_type,
    role,
    *,
    allow_satellite=True,
    risky_asset_limit=None,
    unknown_behavior="REVIEW_REQUIRED",
):
    if account_type == "irp":
        unknown_behavior = "RISK_REDUCE_ONLY"
    return {
        "type": account_type,
        "role": role,
        "allow_satellite": allow_satellite,
        "allowed_asset_classes": ["cash", "equity", "bond"],
        "blocked_product_flags": ["leveraged", "inverse", "futures_like"],
        "max_account_weight_by_asset_class": {},
        "risky_asset_limit": risky_asset_limit,
        "minimum_cash_buffer_ratio": 0.0,
        "unknown_behavior": unknown_behavior,
    }


def test_load_default_account_constraint_config():
    config = load_account_constraint_config()

    assert set(config.accounts) == {"taxable", "isa", "pension", "irp"}
    assert config.accounts["irp"].risky_asset_limit == 0.70
    assert config.accounts["taxable"].unknown_behavior == "REVIEW_REQUIRED"


def test_missing_required_field_fails(tmp_path):
    raw = _config()
    del raw["accounts"]["taxable"]["role"]
    path = tmp_path / "account_constraints.yaml"
    path.write_text(__import__("yaml").safe_dump(raw), encoding="utf-8")

    with pytest.raises(AccountConstraintConfigError, match="role"):
        load_account_constraint_config(path)


def test_unknown_account_type_fails(tmp_path):
    raw = _config()
    raw["accounts"]["mystery"] = _account("mystery", "unknown")
    path = tmp_path / "account_constraints.yaml"
    path.write_text(__import__("yaml").safe_dump(raw), encoding="utf-8")

    with pytest.raises(AccountConstraintConfigError, match="unknown account type"):
        load_account_constraint_config(path)


def test_irp_risky_asset_limit_is_required(tmp_path):
    raw = _config()
    raw["accounts"]["irp"]["risky_asset_limit"] = None
    path = tmp_path / "account_constraints.yaml"
    path.write_text(__import__("yaml").safe_dump(raw), encoding="utf-8")

    with pytest.raises(AccountConstraintConfigError, match="risky_asset_limit"):
        load_account_constraint_config(path)


def test_invalid_unknown_behavior_fails(tmp_path):
    raw = _config(unknown_account_behavior="BUY")
    path = tmp_path / "account_constraints.yaml"
    path.write_text(__import__("yaml").safe_dump(raw), encoding="utf-8")

    with pytest.raises(AccountConstraintConfigError, match="unknown_account_behavior"):
        load_account_constraint_config(path)
