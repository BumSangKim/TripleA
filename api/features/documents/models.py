from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DocumentData:
    id: Optional[int]
    type: str
    title: str
    content: Optional[str]
    tags: Optional[str]
    url: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
