from __future__ import annotations

from datetime import datetime
from typing import Iterable, TypeVar

from api.plugin_boundary.contracts import PluginBoundaryContractError


T = TypeVar("T")


def is_available_for_decision(value: object, decision_time: datetime) -> bool:
    available_at = getattr(value, "available_at", None)
    if available_at is None:
        raise PluginBoundaryContractError("available_at is required for point-in-time decisions")
    return available_at <= decision_time


def filter_available_values(values: Iterable[T], decision_time: datetime) -> list[T]:
    return [value for value in values if is_available_for_decision(value, decision_time)]
