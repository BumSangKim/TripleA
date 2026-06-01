from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "pipeline"


@pytest.fixture
def pipeline_fixture_dir() -> Path:
    return FIXTURE_DIR


@pytest.fixture
def sample_raw_data(pipeline_fixture_dir: Path) -> dict:
    return _load_json(pipeline_fixture_dir / "sample_raw_data.json")


@pytest.fixture
def sample_account_state(pipeline_fixture_dir: Path) -> dict:
    return _load_json(pipeline_fixture_dir / "sample_account_state.json")


@pytest.fixture
def sample_current_positions(pipeline_fixture_dir: Path) -> dict:
    return _load_json(pipeline_fixture_dir / "sample_current_positions.json")


@pytest.fixture
def expected_contract_fields(pipeline_fixture_dir: Path) -> dict:
    return _load_json(pipeline_fixture_dir / "expected_contract_fields.json")


@pytest.fixture(autouse=True)
def block_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked_connect(*args, **kwargs):
        raise AssertionError("network calls are forbidden in pipeline fixture tests")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
