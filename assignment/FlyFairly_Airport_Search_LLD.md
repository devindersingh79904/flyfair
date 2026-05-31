# Fly Fairly Airport Search — Low-Level Design

## 1. Objective

This document defines the implementation-level design for the Fly Fairly airport search prototype.

The system provides a deterministic airport/city/region search API that supports exact IATA matching, city groups, aliases, multilingual queries, region mappings, and fuzzy typo fallback.

---

## 2. Tech Stack

### Backend

```text
Language: Python 3.11+
Framework: FastAPI
Validation: Pydantic
Fuzzy Search: RapidFuzz
Normalization: Unidecode
Testing: pytest
Storage: Local JSON files loaded into memory
```

### Frontend

```text
React
TypeScript
Vite
Fetch API / Axios
Optional Tailwind CSS
```

---

## 3. Backend Folder Structure

```text
backend/
  .env.example
  README.md
  app/
    main.py

    api/
      __init__.py
      airport_routes.py
      health_routes.py

    core/
      __init__.py
      config.py
      constants.py
      logger.py
      middleware.py
      response.py
      exceptions.py

    data/
      airports.json
      aliases.json
      city_groups.json
      regions.json

    models/
      __init__.py
      airport.py
      search.py
      response.py

    services/
      __init__.py
      airport_search_service.py
      index_builder.py
      normalizer.py
      ranker.py

    tests/
      test_airport_search.py
      test_normalizer.py
      test_ranking.py

frontend/
  .env.example
  README.md
  src/
    api/
      airportApi.ts
    constants/
      api.ts
      ui.ts
    components/
      AirportSearchBox.tsx
      AirportResultDropdown.tsx
    types/
      airport.ts

docs/
  HLD.md
  LLD.md
  APPROACH_MEMO.md
  EVAL_CASES.md
  DEMO_SCRIPT.md
```

---


## 4. Environment Configuration

The project should use environment variables for values that change between local development and deployment. Commit `.env.example`, but do not commit `.env`.

### Backend `.env.example`

```env
APP_NAME=fly-fairly-airport-search
APP_ENV=local
API_PREFIX=/api/v1
LOG_LEVEL=INFO
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
AIRPORTS_DATA_PATH=app/data/airports.json
ALIASES_DATA_PATH=app/data/aliases.json
CITY_GROUPS_DATA_PATH=app/data/city_groups.json
REGIONS_DATA_PATH=app/data/regions.json
DEFAULT_SEARCH_LIMIT=10
MAX_SEARCH_LIMIT=20
FUZZY_THRESHOLD=85
```

### Frontend `.env.example`

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_SEARCH_DEBOUNCE_MS=250
VITE_DEFAULT_SEARCH_LIMIT=10
```

---

## 5. CORS Configuration

FastAPI should configure CORS from environment variables so the React TypeScript frontend can call the backend locally.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)
```

For the prototype, allowed origins should include `http://localhost:5173` for Vite and optionally `http://localhost:3000`. Avoid `allow_origins=["*"]` when `allow_credentials=True`.

---

## 6. Constants and String Literal Policy

Repeated values should be centralized so the codebase does not rely on scattered string literals. This is useful for search ranking, API routes, response statuses, error codes, headers, and frontend labels.

### Backend constants

```python
# app/core/constants.py

class ApiRoutes:
    HEALTH = "/health"
    AIRPORT_SEARCH = "/airports/search"

class Headers:
    CORRELATION_ID = "X-Correlation-ID"
    RESPONSE_TIME_MS = "X-Response-Time-Ms"

class ErrorCodes:
    INVALID_QUERY = "INVALID_QUERY"
    INTERNAL_ERROR = "INTERNAL_ERROR"

class MatchReason:
    IATA_EXACT = "IATA_EXACT"
    CITY_CODE_EXACT = "CITY_CODE_EXACT"
    ALIAS_EXACT = "ALIAS_EXACT"
    REGION_EXACT = "REGION_EXACT"
    FUZZY_CITY_MATCH = "FUZZY_CITY_MATCH"
    FUZZY_AIRPORT_MATCH = "FUZZY_AIRPORT_MATCH"
```

### Frontend constants

```ts
// src/constants/api.ts
export const API_ENDPOINTS = {
  AIRPORT_SEARCH: "/airports/search",
  HEALTH: "/health",
} as const;

export const REQUEST_HEADERS = {
  CORRELATION_ID: "X-Correlation-ID",
} as const;

// src/constants/ui.ts
export const SEARCH_LABELS = {
  FROM: "From",
  TO: "To",
  NO_RESULTS: "No matching airports found",
} as const;
```

Avoid over-abstracting one-off strings. Constants are mainly for repeated values and contract-level strings.

---
## 7. API Endpoints

## 4.1 Search Airports

```http
GET /api/v1/airports/search?q={query}&limit={limit}
```

### Query Params

| Param | Type | Required | Default | Description |
|---|---|---:|---:|---|
| `q` | string | yes | - | User search input |
| `limit` | int | no | 10 | Maximum number of results |

### Validation Rules

```text
q must not be empty
q max length: 100
limit min: 1
limit max: 20
```

### Success Response

Search uses `limit`, not page/pageSize pagination. The response still includes metadata so clients can render counts and backend latency consistently.

```json
{
  "timestamp": "2026-05-29T10:15:30.123Z",
  "correlationId": "b7a9c7d8-2e2f-4d5a-91a0-03c7c7fdde21",
  "status": "SUCCESS",
  "message": "Airport search completed successfully",
  "data": {
    "query": "londn",
    "normalizedQuery": "londn",
    "results": [
      {
        "id": "city:LON",
        "type": "CITY_GROUP",
        "displayName": "London",
        "city": "London",
        "country": "United Kingdom",
        "region": null,
        "score": 592,
        "matchReason": "FUZZY_CITY_MATCH",
        "matchedValue": "london",
        "airports": [
          {
            "iata": "LHR",
            "icao": "EGLL",
            "name": "Heathrow Airport",
            "city": "London",
            "country": "United Kingdom",
            "region": "England",
            "lat": 51.4706,
            "lon": -0.4619
          }
        ]
      }
    ]
  },
  "errors": [],
  "meta": {
    "limit": 10,
    "count": 1,
    "hasMore": false,
    "latencyMs": 7
  }
}
```

### Error Response

```json
{
  "timestamp": "2026-05-29T10:15:30.123Z",
  "correlationId": "b7a9c7d8-2e2f-4d5a-91a0-03c7c7fdde21",
  "status": "ERROR",
  "message": "Search query is required",
  "data": null,
  "errors": [
    {
      "code": "INVALID_QUERY",
      "message": "Search query is required",
      "field": "q"
    }
  ],
  "meta": {
    "latencyMs": 1
  }
}
```

---

## 4.2 Health Check

```http
GET /api/v1/health
```

Response:

```json
{
  "timestamp": "2026-05-29T10:15:30.123Z",
  "correlationId": "b7a9c7d8-2e2f-4d5a-91a0-03c7c7fdde21",
  "status": "SUCCESS",
  "message": "Service is healthy",
  "data": {
    "status": "ok",
    "service": "airport-search"
  },
  "errors": [],
  "meta": {}
}
```

---

## 5. Core Data Models

## 5.1 Airport Model

```python
from pydantic import BaseModel
from typing import Optional, List

class Airport(BaseModel):
    iata: str
    icao: Optional[str] = None
    name: str
    city: str
    country: str
    region: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    airport_type: Optional[str] = None
    aliases: List[str] = []
    popularity: int = 0
```

---

## 5.2 City Group Model

```python
from pydantic import BaseModel
from typing import List, Optional

class CityGroup(BaseModel):
    code: str
    display_name: str
    city: str
    country: str
    region: Optional[str] = None
    airport_codes: List[str]
    aliases: List[str] = []
    popularity: int = 0
```

---

## 5.3 Search Result Model

```python
from pydantic import BaseModel
from typing import List, Optional, Literal

class SearchResultAirport(BaseModel):
    iata: str
    icao: Optional[str] = None
    name: str
    city: str
    country: str
    region: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

class SearchResult(BaseModel):
    id: str
    type: Literal["AIRPORT", "CITY_GROUP", "REGION"]
    display_name: str
    city: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    score: int
    match_reason: str
    matched_value: Optional[str] = None
    airports: List[SearchResultAirport]
```

---

## 5.4 API Response Model

All endpoints use a consistent response envelope. The same `correlation_id` is also returned as the `X-Correlation-ID` header and emitted in logs.

```python
from datetime import datetime, timezone
from enum import Enum
from typing import Generic, Optional, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")

class ResponseStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"

class ApiError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None

class ResponseMeta(BaseModel):
    limit: Optional[int] = None
    count: Optional[int] = None
    has_more: Optional[bool] = Field(default=None, alias="hasMore")
    latency_ms: Optional[int] = Field(default=None, alias="latencyMs")

class ApiResponse(BaseModel, Generic[T]):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: str = Field(alias="correlationId")
    status: ResponseStatus
    message: str
    data: Optional[T] = None
    errors: List[ApiError] = Field(default_factory=list)
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
```

---

## 6. Data Files

## 6.1 airports.json

```json
[
  {
    "iata": "BLR",
    "icao": "VOBL",
    "name": "Kempegowda International Airport",
    "city": "Bengaluru",
    "country": "India",
    "region": "Karnataka",
    "lat": 13.1986,
    "lon": 77.7066,
    "airport_type": "large_airport",
    "aliases": ["bangalore", "bengaluru", "blr"],
    "popularity": 85
  },
  {
    "iata": "DPS",
    "icao": "WADD",
    "name": "Ngurah Rai International Airport",
    "city": "Denpasar",
    "country": "Indonesia",
    "region": "Bali",
    "lat": -8.7481,
    "lon": 115.167,
    "airport_type": "large_airport",
    "aliases": ["bali", "denpasar", "ngurah rai", "dps"],
    "popularity": 90
  }
]
```

---

## 6.2 city_groups.json

```json
[
  {
    "code": "LON",
    "display_name": "London",
    "city": "London",
    "country": "United Kingdom",
    "region": "England",
    "airport_codes": ["LHR", "LGW", "STN", "LCY", "LTN"],
    "aliases": ["london", "lon", "london uk"],
    "popularity": 100
  },
  {
    "code": "TYO",
    "display_name": "Tokyo",
    "city": "Tokyo",
    "country": "Japan",
    "region": "Tokyo",
    "airport_codes": ["HND", "NRT"],
    "aliases": ["tokyo", "東京", "tokio"],
    "popularity": 100
  }
]
```

---

## 6.3 aliases.json

```json
{
  "bali": {
    "target_type": "AIRPORT",
    "target_id": "DPS",
    "display_name": "Bali"
  },
  "東京": {
    "target_type": "CITY_GROUP",
    "target_id": "TYO",
    "display_name": "Tokyo"
  },
  "서울": {
    "target_type": "CITY_GROUP",
    "target_id": "SEL",
    "display_name": "Seoul"
  },
  "دبي": {
    "target_type": "AIRPORT",
    "target_id": "DXB",
    "display_name": "Dubai"
  },
  "sao paulo": {
    "target_type": "CITY_GROUP",
    "target_id": "SAO",
    "display_name": "São Paulo"
  }
}
```

---

## 6.4 regions.json

```json
{
  "hawaii": {
    "display_name": "Hawaii",
    "country": "United States",
    "airport_codes": ["HNL", "OGG", "KOA", "LIH"]
  },
  "florida": {
    "display_name": "Florida",
    "country": "United States",
    "airport_codes": ["MIA", "MCO", "FLL", "TPA", "JAX"]
  },
  "ontario": {
    "display_name": "Ontario",
    "country": "Canada",
    "airport_codes": ["YYZ", "YTZ", "YHM", "YKF"]
  }
}
```

---

## 7. Index Builder

The backend builds indexes once at startup.

```python
class SearchIndex:
    airports_by_iata: dict[str, Airport]
    city_groups_by_code: dict[str, CityGroup]
    alias_index: dict[str, AliasTarget]
    region_index: dict[str, RegionTarget]
    searchable_items: list[SearchableItem]
```

### Startup Flow

```text
1. Load airports.json
2. Load city_groups.json
3. Load aliases.json
4. Load regions.json
5. Normalize all aliases
6. Build IATA index
7. Build city code index
8. Build alias index
9. Build region index
10. Build fuzzy searchable item list
```

---

## 8. Normalization Logic

File: `services/normalizer.py`

```python
import re
from unidecode import unidecode


def normalize_query(value: str) -> str:
    if not value:
        return ""

    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)

    # Accent folding for Latin text.
    # Example: São Paulo -> Sao Paulo, München -> Munchen
    folded = unidecode(value)
    folded = folded.strip().lower()
    folded = re.sub(r"\s+", " ", folded)

    return folded


def normalize_raw(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())
```

Important implementation detail:

- Store both raw aliases and normalized aliases.
- Raw aliases preserve scripts like `東京`, `서울`, `دبي`.
- Normalized aliases handle Latin accent folding.

---

## 9. Ranking Constants

File: `services/ranker.py`

```python
class MatchReason:
    IATA_EXACT = "IATA_EXACT"
    CITY_CODE_EXACT = "CITY_CODE_EXACT"
    ALIAS_EXACT = "ALIAS_EXACT"
    CITY_GROUP_EXACT = "CITY_GROUP_EXACT"
    REGION_EXACT = "REGION_EXACT"
    AIRPORT_NAME_EXACT = "AIRPORT_NAME_EXACT"
    CITY_EXACT = "CITY_EXACT"
    FUZZY_CITY_MATCH = "FUZZY_CITY_MATCH"
    FUZZY_AIRPORT_MATCH = "FUZZY_AIRPORT_MATCH"


RANK_BASE = {
    MatchReason.IATA_EXACT: 1000,
    MatchReason.CITY_CODE_EXACT: 950,
    MatchReason.ALIAS_EXACT: 900,
    MatchReason.CITY_GROUP_EXACT: 850,
    MatchReason.REGION_EXACT: 800,
    MatchReason.AIRPORT_NAME_EXACT: 750,
    MatchReason.CITY_EXACT: 700,
    MatchReason.FUZZY_CITY_MATCH: 500,
    MatchReason.FUZZY_AIRPORT_MATCH: 450,
}


def popularity_boost(popularity: int) -> int:
    return min(max(popularity // 10, 0), 30)
```

---

## 10. Search Algorithm

File: `services/airport_search_service.py`

```python
from rapidfuzz import fuzz

FUZZY_THRESHOLD = 85

class AirportSearchService:
    def __init__(self, index: SearchIndex):
        self.index = index

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        raw_query = normalize_raw(query)
        normalized_query = normalize_query(query)
        upper_query = query.strip().upper()

        results: list[SearchResult] = []

        self._match_iata_exact(upper_query, results)
        self._match_city_code_exact(upper_query, results)
        self._match_alias_exact(raw_query, normalized_query, results)
        self._match_region_exact(raw_query, normalized_query, results)
        self._match_exact_text(normalized_query, results)
        self._match_fuzzy(normalized_query, results)

        results = self._dedupe_keep_highest_score(results)
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:limit]
```

---

## 11. Matching Methods

## 11.1 IATA Exact Match

```python
def _match_iata_exact(self, upper_query: str, results: list[SearchResult]) -> None:
    airport = self.index.airports_by_iata.get(upper_query)
    if not airport:
        return

    score = RANK_BASE[MatchReason.IATA_EXACT] + popularity_boost(airport.popularity)
    results.append(to_airport_result(airport, score, MatchReason.IATA_EXACT, upper_query))
```

---

## 11.2 City Code Exact Match

```python
def _match_city_code_exact(self, upper_query: str, results: list[SearchResult]) -> None:
    group = self.index.city_groups_by_code.get(upper_query)
    if not group:
        return

    airports = self._resolve_airports(group.airport_codes)
    score = RANK_BASE[MatchReason.CITY_CODE_EXACT] + popularity_boost(group.popularity)
    results.append(to_city_group_result(group, airports, score, MatchReason.CITY_CODE_EXACT, upper_query))
```

---

## 11.3 Alias Exact Match

```python
def _match_alias_exact(
    self,
    raw_query: str,
    normalized_query: str,
    results: list[SearchResult]
) -> None:
    target = self.index.alias_index.get(raw_query) or self.index.alias_index.get(normalized_query)
    if not target:
        return

    result = self._resolve_alias_target(target, MatchReason.ALIAS_EXACT)
    if result:
        results.append(result)
```

---

## 11.4 Region Exact Match

```python
def _match_region_exact(
    self,
    raw_query: str,
    normalized_query: str,
    results: list[SearchResult]
) -> None:
    region = self.index.region_index.get(raw_query) or self.index.region_index.get(normalized_query)
    if not region:
        return

    airports = self._resolve_airports(region.airport_codes)
    score = RANK_BASE[MatchReason.REGION_EXACT]
    results.append(to_region_result(region, airports, score, MatchReason.REGION_EXACT))
```

---

## 11.5 Fuzzy Match

```python
def _match_fuzzy(self, normalized_query: str, results: list[SearchResult]) -> None:
    for item in self.index.searchable_items:
        fuzzy_score = fuzz.WRatio(normalized_query, item.normalized_text)

        if fuzzy_score < FUZZY_THRESHOLD:
            continue

        base = RANK_BASE[item.fuzzy_match_reason]
        score = base + fuzzy_score + popularity_boost(item.popularity)

        results.append(item.to_search_result(
            score=score,
            match_reason=item.fuzzy_match_reason,
            matched_value=item.normalized_text
        ))
```

---

## 12. Deduplication

A single result can be found through multiple paths. Example: `BLR` can match IATA, alias, and city.

Deduplication rule:

```text
Keep the highest-scoring result per result ID.
```

```python
def _dedupe_keep_highest_score(self, results: list[SearchResult]) -> list[SearchResult]:
    best_by_id: dict[str, SearchResult] = {}

    for result in results:
        existing = best_by_id.get(result.id)
        if existing is None or result.score > existing.score:
            best_by_id[result.id] = result

    return list(best_by_id.values())
```

---

## 13. Logging Design

Use middleware to create a request ID.

Log every search completion:

```python
logger.info(
    "airport_search_completed",
    extra={
        "request_id": request_id,
        "query": query,
        "normalized_query": normalized_query,
        "result_count": len(results),
        "top_result": results[0].display_name if results else None,
        "top_score": results[0].score if results else None,
        "match_reason": results[0].match_reason if results else None,
        "latency_ms": latency_ms,
    }
)
```

Log errors:

```python
logger.exception(
    "airport_search_failed",
    extra={
        "request_id": request_id,
        "query": query
    }
)
```

---

## 14. Middleware

File: `core/middleware.py`

Responsibilities:

- Generate `request_id`
- Add `X-Request-ID` response header
- Track request latency
- Log method/path/status/latency

```python
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = str(latency_ms)

        return response
```

---

## 15. Exception Handling

Use consistent error response.

```python
class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
```

Example errors:

| Code | HTTP | Meaning |
|---|---:|---|
| `INVALID_QUERY` | 400 | Empty or invalid search query |
| `INVALID_LIMIT` | 400 | Limit outside allowed range |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## 16. Frontend Folder Structure

```text
frontend/
  src/
    api/
      airportApi.ts

    components/
      AirportSearchBox.tsx
      AirportResultDropdown.tsx
      SelectedAirportCard.tsx

    types/
      airport.ts

    pages/
      AirportSearchPage.tsx

    App.tsx
    main.tsx
```

---

## 17. Frontend Types

File: `types/airport.ts`

```typescript
export type SearchResultType = "AIRPORT" | "CITY_GROUP" | "REGION";

export interface Airport {
  iata: string;
  icao?: string;
  name: string;
  city: string;
  country: string;
  region?: string;
  lat?: number;
  lon?: number;
}

export interface AirportSearchResult {
  id: string;
  type: SearchResultType;
  displayName: string;
  city?: string;
  country?: string;
  region?: string;
  score: number;
  matchReason: string;
  matchedValue?: string;
  airports: Airport[];
}

export interface AirportSearchData {
  query: string;
  normalizedQuery: string;
  results: AirportSearchResult[];
}

export interface ApiError {
  code: string;
  message: string;
  field?: string;
}

export interface ResponseMeta {
  limit?: number;
  count?: number;
  hasMore?: boolean;
  latencyMs?: number;
}

export interface ApiResponse<T> {
  timestamp: string;
  correlationId: string;
  status: "SUCCESS" | "ERROR";
  message: string;
  data: T | null;
  errors: ApiError[];
  meta: ResponseMeta;
}

export type AirportSearchResponse = ApiResponse<AirportSearchData>;
```

---

## 18. Frontend API Client

File: `api/airportApi.ts`

```typescript
export async function searchAirports(
  query: string,
  limit = 10
): Promise<AirportSearchData> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });

  const response = await fetch(`/api/v1/airports/search?${params.toString()}`);
  const body: AirportSearchResponse = await response.json();

  if (!response.ok || body.status === "ERROR" || !body.data) {
    throw new Error(body.errors?.[0]?.message ?? body.message ?? "Failed to search airports");
  }

  return body.data;
}
```

---

## 19. AirportSearchBox Behavior

Responsibilities:

- Keep input state
- Debounce query by 250 ms
- Call search API when query length >= 2
- Show dropdown results
- Allow result selection
- Show selected result

Pseudo-flow:

```text
onChange(input)
  setQuery(input)
  if input length < 2:
    clear results
    return
  debounce 250ms
  call search API
  show results
```

---

## 20. Test Plan

## 20.1 Normalizer Tests

```python
def test_accent_folding():
    assert normalize_query("São Paulo") == "sao paulo"


def test_whitespace_cleanup():
    assert normalize_query("  New   York  ") == "new york"
```

---

## 20.2 Search Eval Tests

```python
def test_bali_returns_dps_not_balikpapan(search_service):
    results = search_service.search("Bali")
    assert results[0].airports[0].iata == "DPS"
    assert results[0].match_reason == "ALIAS_EXACT"


def test_londn_returns_london(search_service):
    results = search_service.search("Londn")
    assert results[0].display_name == "London"
    assert results[0].match_reason == "FUZZY_CITY_MATCH"


def test_tokyo_japanese_returns_tokyo(search_service):
    results = search_service.search("東京")
    assert results[0].display_name == "Tokyo"
```

---

## 20.3 Required Eval Cases

| Test | Query | Expected Top Result |
|---|---|---|
| State search | `Hawaii` | Region group with HNL, OGG, KOA, LIH |
| Tourism alias | `Bali` | DPS |
| Bad fuzzy prevention | `Florida` | US Florida airports, not Chile |
| City name mapping | `Manama` | BAH |
| City alias | `Bengaluru` | BLR |
| IATA reverse | `TUL` | Tulsa |
| Friendly city | `Brussels` | BRU |
| Typo tolerance | `Londn` | London |
| Multi-airport code | `LON` | London city group |
| Japanese | `東京` | Tokyo |
| Chinese | `北京` | Beijing |
| Korean | `서울` | Seoul |
| Arabic | `دبي` | Dubai |
| Accent folding | `Sao Paulo` | São Paulo group |

---

## 21. Runtime Complexity

Let:

```text
N = number of searchable items
A = number of aliases
```

Exact lookups:

```text
O(1)
```

Fuzzy fallback:

```text
O(N)
```

For the prototype dataset, this is acceptable. In production, fuzzy search can move to:

- BK-tree
- Trigram index
- Typesense
- Meilisearch
- Elasticsearch/OpenSearch

---

## 22. Production Hardening Ideas

If extended beyond prototype:

- Replace local JSON with ingestion pipeline
- Add scheduled data refresh
- Add search analytics
- Add click-based ranking
- Add airport traffic/popularity data
- Add locale-aware boosting
- Add geolocation boosting
- Add admin alias curation
- Add caching for hot queries
- Add contract tests for API response
- Add performance tests for p95 latency

---

## 23. Implementation Priority

For the take-home prototype, implement in this order:

```text
1. Data files with required failure cases
2. Normalizer
3. Index builder
4. Exact IATA match
5. Alias match
6. City group match
7. Region match
8. RapidFuzz fallback
9. Deduping and ranking
10. Search API
11. Tests
12. React TypeScript UI
13. Logging and memo polishing
```

---

## 24. Final LLD Summary

The low-level design uses a deterministic, rule-based search pipeline backed by curated local data and RapidFuzz typo fallback.

The most important implementation principle is:

```text
Never let fuzzy matching override exact semantic intent.
```

This is why the system checks IATA, city code, alias, city group, and region mappings before fuzzy search.

---

## 24. Production API Contract Addendum

This section defines the common response envelope, pagination metadata, correlation ID handling, and structured logging contract.

## 24.1 Response Status Enum

```python
from enum import Enum

class ResponseStatus(str, Enum):
    SUCCESS = "SUCCESS"
    ERROR = "ERROR"
```

## 24.2 Error Detail Model

```python
from typing import Optional
from pydantic import BaseModel

class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
```

## 24.3 Pagination / Meta Model

For autocomplete, `limit` is enough. We still return a `meta` object for a consistent API contract.

```python
from typing import Optional
from pydantic import BaseModel

class ResponseMeta(BaseModel):
    limit: Optional[int] = None
    count: Optional[int] = None
    has_more: bool = False
    latency_ms: Optional[float] = None
```

## 24.4 Generic API Response Model

```python
from datetime import datetime, timezone
from typing import Generic, Optional, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: str
    status: ResponseStatus
    message: str
    data: Optional[T] = None
    errors: List[ErrorDetail] = Field(default_factory=list)
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
```

## 24.5 Success Response Example

```json
{
  "timestamp": "2026-05-29T10:15:30.123Z",
  "correlationId": "b7a9c7d8-2e2f-4d5a-91a0-03c7c7fdde21",
  "status": "SUCCESS",
  "message": "Airport search completed successfully",
  "data": {
    "query": "londn",
    "normalizedQuery": "londn",
    "results": [
      {
        "id": "city:LON",
        "type": "CITY_GROUP",
        "displayName": "London",
        "country": "United Kingdom",
        "score": 592,
        "matchReason": "FUZZY_CITY_MATCH",
        "airports": [
          {
            "iata": "LHR",
            "name": "Heathrow Airport",
            "city": "London",
            "country": "United Kingdom"
          }
        ]
      }
    ]
  },
  "errors": [],
  "meta": {
    "limit": 10,
    "count": 1,
    "hasMore": false,
    "latencyMs": 7
  }
}
```

## 24.6 Error Response Example

```json
{
  "timestamp": "2026-05-29T10:15:30.123Z",
  "correlationId": "b7a9c7d8-2e2f-4d5a-91a0-03c7c7fdde21",
  "status": "ERROR",
  "message": "Invalid search query",
  "data": null,
  "errors": [
    {
      "code": "INVALID_QUERY",
      "field": "q",
      "message": "Search query must not be empty"
    }
  ],
  "meta": {}
}
```

## 24.7 Correlation ID Middleware

```python
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Response-Time-Ms"] = str(latency_ms)
        return response
```

## 24.8 Search API with Meta

```python
@router.get("/search", response_model=ApiResponse[AirportSearchData])
def search_airports(
    q: str,
    limit: int = Query(default=10, ge=1, le=20),
    request: Request = None,
):
    correlation_id = request.state.correlation_id
    start = time.perf_counter()

    result = search_service.search(q, limit)
    latency_ms = round((time.perf_counter() - start) * 1000, 2)

    return ApiResponse[AirportSearchData](
        correlation_id=correlation_id,
        status=ResponseStatus.SUCCESS,
        message="Airport search completed successfully",
        data=result,
        errors=[],
        meta=ResponseMeta(
            limit=limit,
            count=len(result.results),
            has_more=False,
            latency_ms=latency_ms,
        ),
    )
```

## 24.9 Structured Logging

Log one event per completed search.

```python
logger.info(
    "airport_search_completed",
    extra={
        "correlation_id": correlation_id,
        "query": q,
        "normalized_query": result.normalized_query,
        "result_count": len(result.results),
        "top_result": result.results[0].display_name if result.results else None,
        "top_score": result.results[0].score if result.results else None,
        "match_reason": result.results[0].match_reason if result.results else None,
        "latency_ms": latency_ms,
    },
)
```

Log exceptions with the same correlation ID.

```python
logger.exception(
    "airport_search_failed",
    extra={
        "correlation_id": correlation_id,
        "query": q,
    },
)
```

## 24.10 Why Full Pagination Is Not Required

The search endpoint is an autocomplete endpoint. Users need the best ranked 5-10 suggestions, not a browsable catalog of airports. Therefore:

- `limit` is supported.
- `count` is returned.
- `hasMore` is always false for the prototype.
- `page`, `offset`, and cursor pagination are intentionally excluded.

This keeps the API production-like without overengineering the assignment.


---

## 25. Documentation Folder

A small `docs/` folder should be included because the submission is evaluated heavily on judgment and explanation, not only working code.

```text
docs/
  HLD.md
  LLD.md
  APPROACH_MEMO.md
  EVAL_CASES.md
  DEMO_SCRIPT.md
```

Recommended content:

- `HLD.md`: architecture, tradeoffs, why no runtime DB, why no runtime LLM.
- `LLD.md`: API contract, models, ranking constants, CORS, env, logging, and tests.
- `APPROACH_MEMO.md`: one-page submission memo.
- `EVAL_CASES.md`: required failure cases and expected outputs.
- `DEMO_SCRIPT.md`: 10-15 minute recorded walkthrough outline.

This is enough documentation for the take-home. Avoid adding large enterprise-style docs that do not help the reviewer.

---

## 26. Final Implementation Hygiene Checklist

- Backend has `.env.example`; local `.env` is ignored.
- Frontend has `.env.example`; local `.env` is ignored.
- Backend CORS is configured from settings.
- Repeated backend contract strings are in constants/enums.
- Repeated frontend route/header/UI strings are in constants.
- API responses use the standard envelope.
- Search uses `limit`, not full `page/pageSize` pagination.
- Logs include `timestamp`, `level`, `correlationId`, `file`, `line`, `event`, `query`, `resultCount`, and `latencyMs`.
- `taskId` is not required for this synchronous search API.
- Docs folder contains HLD, LLD, memo, eval cases, and demo script.
