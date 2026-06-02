from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from api.features.backtests.ai_capex_token_tuning_execution_test import (
    run_ai_capex_token_tuning_execution_test,
)


FIXTURE_DIR = Path("tests/fixtures/ai_capex_token_tuning")


def test_future_data_is_excluded_and_reported_in_tuning_report():
    report = _report(_snapshots_with_future_probe())

    assert report["leakage_check_passed"] is True
    assert report["leakage_warnings"]
    assert all(warning["code"] == "FUTURE_INPUT_EXCLUDED" for warning in report["leakage_warnings"])
    assert all(
        "future.leakage_probe" in warning["excluded_metric_keys"]
        for warning in report["leakage_warnings"]
    )


def test_future_data_include_and_exclude_have_same_available_output():
    with_future = _report(_snapshots_with_future_probe())
    without_future = _report(_snapshots_without_future_probe())

    signatures_with_future = _output_signatures(with_future)
    signatures_without_future = _output_signatures(without_future)
    objective_with_future = _objective_scores(with_future)
    objective_without_future = _objective_scores(without_future)

    assert signatures_with_future == signatures_without_future
    assert objective_with_future == objective_without_future


def test_future_data_does_not_improve_selected_candidate_objective():
    with_future = _report(_snapshots_with_future_probe())
    without_future = _report(_snapshots_without_future_probe())
    selected = with_future["selected_candidate_id"]

    assert selected == without_future["selected_candidate_id"]
    assert _objective_scores(with_future)[selected] == _objective_scores(without_future)[selected]
    assert with_future["production_ready"] is False


def _report(snapshots: list[dict]) -> dict:
    candidate_grid = json.loads((FIXTURE_DIR / "candidate_grid_smoke.json").read_text(encoding="utf-8"))
    return run_ai_capex_token_tuning_execution_test(candidate_grid=candidate_grid, snapshots=snapshots)


def _snapshots_with_future_probe() -> list[dict]:
    fixture = json.loads((FIXTURE_DIR / "synthetic_two_memory_cycles.json").read_text(encoding="utf-8"))
    return fixture["snapshots"]


def _snapshots_without_future_probe() -> list[dict]:
    snapshots = deepcopy(_snapshots_with_future_probe())
    for snapshot in snapshots:
        snapshot["capex_series"] = [
            row for row in snapshot["capex_series"] if row["metric_key"] != "future.leakage_probe"
        ]
    return snapshots


def _output_signatures(report: dict) -> dict[str, str]:
    return {
        result["candidate"]["candidate_id"]: result["output_signature"]
        for result in report["candidates"]
    }


def _objective_scores(report: dict) -> dict[str, float]:
    return {
        result["candidate"]["candidate_id"]: result["objective_score"]
        for result in report["candidates"]
    }
