from __future__ import annotations

from datetime import date, datetime


def test_pipeline_fixture_json_files_parse(
    sample_raw_data: dict,
    sample_account_state: dict,
    sample_current_positions: dict,
    expected_contract_fields: dict,
) -> None:
    assert sample_raw_data["rows"]
    assert sample_account_state["accounts"]
    assert sample_current_positions["positions"]
    assert expected_contract_fields


def test_raw_data_rows_have_required_timing_and_value_fields(sample_raw_data: dict) -> None:
    decision_date = date.fromisoformat(sample_raw_data["decision_date"])
    required_fields = {"source", "as_of_date", "available_at", "value"}

    for row in sample_raw_data["rows"]:
        assert required_fields <= set(row)
        assert datetime.fromisoformat(row["available_at"]).date() <= decision_date


def test_account_fixture_contains_id_type_and_constraints(sample_account_state: dict) -> None:
    account_types = set()

    for account in sample_account_state["accounts"]:
        assert account["account_id"]
        assert account["account_type"]
        assert account["constraints"]
        assert account["constraints"]["automatic_execution_allowed"] is False
        account_types.add(account["account_type"])

    assert {"GENERAL", "IRP"} <= account_types


def test_current_positions_include_account_asset_and_weight(sample_current_positions: dict) -> None:
    for position in sample_current_positions["positions"]:
        assert position["account_id"]
        assert position["asset_id"]
        assert 0 <= position["current_weight"] <= 1


def test_expected_contract_fields_are_non_empty(expected_contract_fields: dict) -> None:
    for fields in expected_contract_fields.values():
        assert fields
