from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DocumentSchema(BaseModel):
    id: Optional[int] = None
    type: str = "memo"
    title: str
    content: Optional[str] = None
    tags: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
