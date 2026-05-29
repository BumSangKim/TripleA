from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from api.features.documents.dependencies import get_documents_service
from api.features.documents.schemas import DocumentSchema
from api.features.documents.service import DocumentsService

router = APIRouter(tags=["documents"])


@router.get("/api/documents", response_model=List[DocumentSchema])
def list_documents(
    type: Optional[str] = None,
    limit: int = 100,
    svc: DocumentsService = Depends(get_documents_service),
):
    rows = svc.list_documents(type, limit)
    return [DocumentSchema(**r) for r in rows]


@router.get("/api/documents/counts")
def document_counts(svc: DocumentsService = Depends(get_documents_service)):
    return svc.count_by_type()


@router.post("/api/documents", response_model=DocumentSchema)
def create_document(
    doc: DocumentSchema,
    svc: DocumentsService = Depends(get_documents_service),
):
    row = svc.create_document(doc)
    return DocumentSchema(**row)


@router.put("/api/documents/{doc_id}", response_model=DocumentSchema)
def update_document(
    doc_id: int,
    doc: DocumentSchema,
    svc: DocumentsService = Depends(get_documents_service),
):
    row = svc.update_document(doc_id, doc)
    if row is None:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    return DocumentSchema(**row)


@router.delete("/api/documents/{doc_id}")
def delete_document(
    doc_id: int,
    svc: DocumentsService = Depends(get_documents_service),
):
    found = svc.delete_document(doc_id)
    if not found:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다")
    return {"ok": True, "deleted": doc_id}
