from __future__ import annotations

from fastapi import APIRouter, Depends

from api.features.search.dependencies import get_search_service
from api.features.search.schemas import SearchResponse, SearchResultItem
from api.features.search.service import SearchService

router = APIRouter(tags=["system"])


@router.get("/api/search", response_model=SearchResponse)
def search(
    q: str = "",
    svc: SearchService = Depends(get_search_service),
):
    results = svc.search(q)
    return SearchResponse(
        results=[SearchResultItem(**r) for r in results]
    )
