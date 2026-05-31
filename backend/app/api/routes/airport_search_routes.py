from fastapi import APIRouter, Request, Query, Depends
from app.core.errors import InvalidQueryException
from app.core.response_builder import build_success_response
from app.services.airport_search_service import AirportSearchService
from app.models.response_models import ApiResponse, SearchResponseData
from app.core.constants import SearchBounds

router = APIRouter()

def get_search_service(request: Request) -> AirportSearchService:
    """Dependency provider retrieving the shared search service instance from app state."""
    return request.app.state.search_service

@router.get("/airports/search", response_model=ApiResponse[SearchResponseData])
async def search_airports(
    request: Request,
    q: str = Query(..., description="Search query string"),
    limit: int = Query(
        default=SearchBounds.DEFAULT_LIMIT,
        ge=SearchBounds.MIN_LIMIT,
        le=SearchBounds.MAX_LIMIT,
        description="Maximum number of search results (1 to 20)"
    ),
    service: AirportSearchService = Depends(get_search_service)
):
    """Airport search endpoint supporting cities, regions, aliases, typos, and native scripts."""
    correlation_id = getattr(request.state, "correlation_id", "")
    
    # Validate non-empty, trimmed query
    trimmed_q = q.strip()
    if not trimmed_q:
        raise InvalidQueryException(
            message="Search query must contain at least 1 character",
            field="q"
        )
        
    # Execute search logic
    results_data, latency_ms = service.search(trimmed_q, limit)
    
    # Prepare standard metadata
    meta = {
        "limit": limit,
        "count": len(results_data.results),
        "hasMore": False,  # Autocomplete search is limit-bound
        "latencyMs": latency_ms
    }
    
    return build_success_response(
        data=results_data,
        message="Airport search completed successfully",
        meta=meta,
        correlation_id=correlation_id
    )
