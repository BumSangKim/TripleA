from __future__ import annotations

import sqlite3
from typing import Generator

from fastapi import Depends

from api.db.connection import get_conn
from api.features.documents.repository import DocumentsRepository
from api.features.documents.service import DocumentsService


def get_db() -> Generator[sqlite3.Connection, None, None]:
    with get_conn() as conn:
        yield conn


def get_documents_repository(conn: sqlite3.Connection = Depends(get_db)) -> DocumentsRepository:
    return DocumentsRepository(conn)


def get_documents_service(
    repo: DocumentsRepository = Depends(get_documents_repository),
) -> DocumentsService:
    return DocumentsService(repo)
