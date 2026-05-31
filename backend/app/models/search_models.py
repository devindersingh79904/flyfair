from pydantic import BaseModel
from typing import List, Optional
from app.core.constants import ResultType, MatchReason

class NormalizedQuery(BaseModel):
    raw: str
    lower: str
    normalized: str
    upper: str
    rawNormalized: str
    latinFoldedNormalized: str

class SearchResultAirport(BaseModel):
    id: Optional[str] = None
    iata: str
    name: str
    city: str
    region: Optional[str] = None
    country: str
    countryCode: str

class SearchResult(BaseModel):
    id: str
    type: ResultType
    code: Optional[str] = None
    displayName: str
    city: Optional[str] = None
    region: Optional[str] = None
    country: str
    countryCode: str
    score: int
    matchReason: MatchReason
    airports: List[SearchResultAirport]
