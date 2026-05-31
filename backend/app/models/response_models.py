from pydantic import BaseModel, Field
from typing import List, Optional, Generic, TypeVar, Any
from app.core.constants import ResponseStatus
from app.models.search_models import SearchResult

T = TypeVar('T')

class ApiError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None

class ResponseMeta(BaseModel):
    limit: Optional[int] = None
    count: Optional[int] = None
    hasMore: Optional[bool] = None
    latencyMs: Optional[int] = None

class ApiResponse(BaseModel, Generic[T]):
    timestamp: str
    correlationId: str
    status: ResponseStatus
    message: str
    data: Optional[T] = None
    errors: List[ApiError] = Field(default_factory=list)
    meta: ResponseMeta

class SearchResponseData(BaseModel):
    results: List[SearchResult]
