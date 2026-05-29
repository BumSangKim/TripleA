from __future__ import annotations

from api.features.documents.schemas import DocumentSchema
from api.features.documents.models import DocumentData
from api.features.documents.ports import IDocumentsRepository


def test_schema_instantiation():
    doc = DocumentSchema(title="Test Doc", type="memo")
    assert doc.title == "Test Doc"


def test_model_instantiation():
    doc = DocumentData(id=1, type="memo", title="Test", content=None, tags=None, url=None, created_at=None, updated_at=None)
    assert doc.type == "memo"


def test_protocol_import():
    assert IDocumentsRepository is not None
