from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    type: str
    key: str
    title: str
    url: str


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
