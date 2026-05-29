from __future__ import annotations

from typing import Any, Optional

from api.features.documents.ports import IDocumentsRepository


class DocumentsService:
    def __init__(self, repo: IDocumentsRepository) -> None:
        self._repo = repo

    def list_documents(self, type: Optional[str] = None, limit: int = 100) -> list[Any]:
        return self._repo.list_documents(type, limit)

    def count_by_type(self) -> dict[str, int]:
        return self._repo.count_by_type()

    def create_document(self, doc: Any) -> Any:
        return self._repo.create_document(doc)

    def update_document(self, doc_id: int, doc: Any) -> Any:
        return self._repo.update_document(doc_id, doc)

    def delete_document(self, doc_id: int) -> bool:
        return self._repo.delete_document(doc_id)
