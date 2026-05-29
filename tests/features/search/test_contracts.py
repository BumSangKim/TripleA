from __future__ import annotations

from api.features.search.schemas import SearchResponse, SearchResultItem
from api.features.search.models import SearchResultData
from api.features.search.ports import ISearchRepository


def test_schema_instantiation():
    resp = SearchResponse(results=[
        SearchResultItem(type="macro", key="GDP", title="GDP", url="/macro")
    ])
    assert len(resp.results) == 1


def test_model_instantiation():
    data = SearchResultData(type="document", key="1", title="Test", url="/documents")
    assert data.type == "document"


def test_protocol_import():
    assert ISearchRepository is not None
