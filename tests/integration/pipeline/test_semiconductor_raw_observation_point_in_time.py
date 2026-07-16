from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from api.data.adapters.semiconductor_fixtures import FixtureSemiconductorObservationRepository


FIXTURE_PATH = Path("tests/fixtures/semiconductor/raw_observations.json")


def test_fixture_ingestion_to_snapshot_excludes_future_release_and_later_revision():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    repository = FixtureSemiconductorObservationRepository.from_rows(payload["observations"])
    snapshot = repository.build_snapshot(
        snapshot_id="semiconductor-pit-20260210",
        decision_time=datetime.fromisoformat("2026-02-10T00:00:00+00:00"),
        canonical_series_ids=(
            "semiconductor.memory.dram_spot_price_index",
            "semiconductor.global.wafer_shipments_index",
            "semiconductor.inventory.channel_days",
        ),
    )

    dram = snapshot.get_available("semiconductor.memory.dram_spot_price_index")

    assert dram is not None
    assert dram.value == 100.0
    assert dram.revision_id == "dram-2026-01-initial"
    assert "semiconductor.global.wafer_shipments_index" not in snapshot.points
    assert "semiconductor.inventory.channel_days" not in snapshot.points
    assert {warning.code for warning in snapshot.warnings} == {
        "SEMICONDUCTOR_RAW_OBSERVATION_UNAVAILABLE",
        "SEMICONDUCTOR_RAW_OBSERVATION_MISSING",
    }
