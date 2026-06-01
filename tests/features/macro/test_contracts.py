from __future__ import annotations

from api.features.macro.ports import IMacroRepository


def test_imacro_repository_protocol_importable():
    assert IMacroRepository is not None
