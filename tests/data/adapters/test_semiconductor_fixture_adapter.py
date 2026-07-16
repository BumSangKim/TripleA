from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository


FIXTURE_PATH = Path("tests/fixtures/semiconductor/raw_observations.json")


def _repository() -> FixtureSemiconductorObservationRepository:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return FixtureSemiconductorObservationRepository.from_rows(payload["observations"])


def test_selects_latest_eligible_vintage_without_using_future_revision():
    repository = _repository()
    series_id = "semiconductor.memory.dram_spot_price_index"

    before_revision = repository.select_latest(series_id, decision_time=datetime.fromisoformat("2026-02-10T00:00:00+00:00"))
    after_revision = repository.select_latest(series_id, decision_time=datetime.fromisoformat("2026-02-25T00:00:00+00:00"))

    assert before_revision is not None
    assert after_revision is not None
    assert str(before_revision.value) == "100.0"
    assert before_revision.revision_id == "dram-2026-01-initial"
    assert str(after_revision.value) == "104.0"
    assert after_revision.revision_id == "dram-2026-01-revision-1"


def test_future_observation_is_unavailable_before_its_release_time():
    repository = _repository()

    selected = repository.select_latest(
        "semiconductor.global.wafer_shipments_index",
        decision_time=datetime.fromisoformat("2026-03-01T00:00:00+00:00"),
    )

    assert selected is None
