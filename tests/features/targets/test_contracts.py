from __future__ import annotations

from api.features.targets.models import TargetUpdateData
from api.features.targets.ports import ITargetsRepository
from api.features.targets.schemas import TargetUpdateResponse


def test_target_update_response_schema():
    r = TargetUpdateResponse(ok=True)
    assert r.ok is True


def test_target_update_data_model():
    d = TargetUpdateData(asset_class="equity", target_value=60.0)
    assert d.asset_class == "equity"
    assert d.warning_thr == 3.0


def test_itargets_repository_protocol_importable():
    assert ITargetsRepository is not None
