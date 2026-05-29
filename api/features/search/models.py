from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResultData:
    type: str
    key: str
    title: str
    url: str
