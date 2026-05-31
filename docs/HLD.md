# Fly Fairly Airport Search — High-Level Design

## 1. Problem Statement

Fly Fairly needs a reliable airport search flow that can handle real user search behavior, including:

- IATA codes: `JFK`, `TUL`, `CTA`
- City names: `London`, `Manama`, `Bengaluru`
- Multi-airport city codes: `LON`
- Regions/states/tourism aliases: `Hawaii`, `Ontario`, `Bali`, `Goa`
- Typos: `Londn`
- Accents and alternate spellings: `Sao Paulo` / `São Paulo`, `München` / `Munich`
- Multilingual and multi-script inputs: `東京`, `北京`, `서울`, `دبي`
- Ambiguous names: `London` UK vs London, Ontario vs London, Kentucky

The goal is not to build a complete flight-booking system. The goal is to build a deterministic, explainable, low-latency airport search prototype with clear ranking rules, multilingual alias handling, and an evaluation harness.

---

## 2. Scope

### In Scope

- React + TypeScript frontend with two airport search fields: `From` and `To`
- Python FastAPI backend
- `/api/v1/airports/search` endpoint
- Local airport/alias/city-group data
- Query normalization
- Exact IATA matching
- Alias matching
- City group matching
- Region/state matching
- Fuzzy typo matching using RapidFuzz
- Ranking and disambiguation
- Structured logging
- CORS configuration for local frontend integration
- Environment-based configuration using `.env` and `.env.example`
- Project docs folder with setup, architecture, and demo notes
- Shared constants to avoid scattered string literals
- Basic regression tests/eval harness
- One-page approach memo and recorded walkthrough support

### Out of Scope

- Real flight pricing/search
- Authentication
- User accounts
- Payments
- Admin panel
- Full production ingestion pipeline
- Runtime LLM calls
- PostgreSQL or Elasticsearch dependency
- Full global airport completeness

---

## 3. Key Design Decision

For a 3–5 hour take-home assignment, the system should optimize for correctness on known failure classes, explainability, and fast demoability.

### Chosen Architecture

```text
React TypeScript UI
        |
        | HTTP GET /api/v1/airports/search?q=londn&limit=10
        v
Python FastAPI Backend
        |
        | SearchService
        v
In-Memory Search Index
        |
        | Built from local JSON data
        v
Airport Data + Aliases + City Groups + Region Mappings
```

### Why No Runtime DB?

Airport autocomplete is a small, read-heavy search problem for this prototype. Loading curated data into memory gives:

- Very low latency
- Simple local setup
- Deterministic behavior
- Easy testing
- No external runtime dependency

A database can be added later for ingestion, admin tooling, and larger datasets, but it is not required for this assignment.

### Why No Runtime LLM?

Search autocomplete must be deterministic, fast, cheap, and auditable. Runtime LLM calls are not appropriate for every keystroke because they can be slow, expensive, and occasionally hallucinate airport mappings.

LLMs are useful during development for:

- Brainstorming edge cases
- Reviewing ranking logic
- Generating multilingual alias candidates
- Creating eval cases
- Reviewing memo clarity

But final search behavior should be implemented with explicit rules and testable data.

---

## 4. Data Sources and Data Strategy

### Prototype Data Strategy

Use local curated JSON files:

```text
backend/app/data/airports.json
backend/app/data/aliases.json
backend/app/data/city_groups.json
backend/app/data/regions.json
```

### Production Data Sources

Potential production sources:

- OurAirports for airport metadata
- GeoNames for alternate names, transliterations, and multilingual names
- OpenStreetMap/Wikidata/Wikipedia for city aliases and tourism/region terms
- Internal booking/search logs for real user aliases and ranking signals

### Data Cleaning Rules

For the prototype, keep only commercially relevant airports.

Keep:

- Large airports
- Medium airports
- Airports with valid IATA code
- Manually selected small airports only if commercially relevant

Remove:

- Heliports
- Seaplane bases
- Closed airports
- Military-only airports
- Rows without IATA codes unless needed for city grouping

---

## 5. Data Model Overview

### Airport

```json
{
  "iata": "BLR",
  "icao": "VOBL",
  "name": "Kempegowda International Airport",
  "city": "Bengaluru",
  "country": "India",
  "region": "Karnataka",
  "lat": 13.1986,
  "lon": 77.7066,
  "type": "large_airport",
  "aliases": ["bangalore", "bengaluru", "blr"]
}
```

### City Group

```json
{
  "code": "LON",
  "displayName": "London",
  "country": "United Kingdom",
  "airports": ["LHR", "LGW", "STN", "LCY", "LTN"],
  "aliases": ["london", "lon"]
}
```

### Alias Mapping

```json
{
  "bali": {
    "type": "CITY_ALIAS",
    "target": "DPS",
    "displayName": "Bali"
  },
  "東京": {
    "type": "CITY_GROUP_ALIAS",
    "target": "TYO",
    "displayName": "Tokyo"
  }
}
```

---

## 6. Search Flow

```text
1. Receive query
2. Validate query
3. Normalize query
4. Check exact IATA code
5. Check exact city/multi-airport code
6. Check exact alias
7. Check region/state mapping
8. Check exact city/airport name
9. Run RapidFuzz typo fallback
10. Dedupe results
11. Rank results
12. Return top N
13. Log query, match reason, latency, and result count
```

---

## 7. Ranking Strategy

The ranking principle is:

> Exact meaning beats fuzzy similarity.

Base ranking priority:

| Match Type | Base Score | Example |
|---|---:|---|
| IATA exact | 1000 | `JFK` → JFK |
| City code exact | 950 | `LON` → London all airports |
| Alias exact | 900 | `Bali` → DPS |
| City group exact | 850 | `Tokyo` → HND/NRT |
| Region exact | 800 | `Hawaii` → HNL/OGG/KOA/LIH |
| Airport name exact | 750 | `Heathrow` → LHR |
| City exact | 700 | `Manama` → BAH |
| Fuzzy city | 500 + fuzzy score | `Londn` → London |
| Fuzzy airport | 450 + fuzzy score | typo in airport name |

Small popularity boosts are allowed but must never override exact match priority.

Example:

```text
Bali exact alias -> DPS, score 900
Balikpapan fuzzy -> BPN, score 580
Result: DPS wins
```

---

## 8. Multilingual Support

The prototype supports multilingual search through a curated alias index.

Examples:

| Input | Normalized Target | Result |
|---|---|---|
| `東京` | Tokyo | HND, NRT |
| `北京` | Beijing | PEK, PKX |
| `서울` | Seoul | ICN, GMP |
| `دبي` | Dubai | DXB |
| `São Paulo` | Sao Paulo | GRU, CGH, VCP |
| `Sao Paulo` | Sao Paulo | GRU, CGH, VCP |

Normalization includes:

- Lowercasing
- Whitespace cleanup
- Accent folding for Latin text
- Preserving raw non-Latin aliases
- Exact alias lookup before fuzzy matching

---

## 9. API Design

### Search Airport

```http
GET /api/v1/airports/search?q=londn&limit=10
```

Response uses the standard API envelope with limit-based metadata, not full page-based pagination:

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

### Health Check

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
    "status": "ok"
  },
  "errors": [],
  "meta": {}
}
```

---

## 10. Frontend Design

### Components

```text
AirportSearchPage
  ├── AirportSearchBox: From
  ├── AirportSearchBox: To
  ├── AirportResultDropdown
  └── SelectedAirportCard
```

### UX Behavior

- User types 2+ characters
- Debounce API call by 200–300 ms
- Show loading state
- Show top ranked results
- Show result type: Airport / City Group / Region
- Show IATA codes for clarity
- Allow selecting From and To independently

---

## 11. Observability

Structured logs should include:

```json
{
  "event": "airport_search_completed",
  "requestId": "req-123",
  "query": "Londn",
  "normalizedQuery": "londn",
  "resultCount": 3,
  "topResult": "London, United Kingdom",
  "topScore": 592,
  "matchReason": "FUZZY_CITY_MATCH",
  "latencyMs": 8
}
```

This supports debugging, demo explanation, and production evaluation.

---

## 12. Evaluation Strategy

### Regression Test Cases

| Query | Expected Behavior |
|---|---|
| `Hawaii` | Returns HNL, OGG, KOA, LIH |
| `Bali` | Returns DPS, not Balikpapan |
| `Florida` | Returns US Florida airports, not La Florida Chile |
| `Manama` | Returns BAH |
| `Bengaluru` | Returns BLR |
| `TUL` | Returns Tulsa |
| `CTA` | Returns Catania |
| `Brussels` | Returns BRU |
| `Londn` | Returns London |
| `LON` | Returns London multi-airport group |
| `London` | Disambiguates UK, Ontario, Kentucky |
| `東京` | Returns Tokyo airports |
| `北京` | Returns Beijing airports |
| `서울` | Returns Seoul airports |
| `دبي` | Returns Dubai |
| `Sao Paulo` | Same as `São Paulo` |

### Production Metrics

- Search zero-result rate
- Top result click-through rate
- Correction/re-query rate
- Latency p50/p95/p99
- Popular query failures
- Search-to-booking conversion
- Alias coverage by locale
- Fuzzy fallback usage rate

---

## 13. Future Improvements

With more time:

- Add real ingestion from OurAirports and GeoNames
- Add search analytics feedback loop
- Add learned ranking from click logs
- Add airport popularity/passenger traffic boost
- Add Elasticsearch/OpenSearch or Typesense if dataset grows
- Add admin tool for alias curation
- Add locale-aware ranking
- Add geolocation-based boost
- Add automated multilingual alias generation with human review

---


## 14. Engineering Hygiene and Project Structure

The prototype should include a small `docs/` folder because the assignment is judged not only on code but also on reasoning and walkthrough quality. The docs should be concise and useful, not a large enterprise design pack.

Recommended repository-level documentation:

```text
docs/
  HLD.md                 # High-level architecture and tradeoffs
  LLD.md                 # Implementation-level design
  APPROACH_MEMO.md       # One-page submission memo
  EVAL_CASES.md          # Search test cases and expected behavior
  DEMO_SCRIPT.md         # 10-15 minute walkthrough outline
```

Backend and frontend should avoid scattered string literals for repeated values. Constants/enums should be used for API routes, response statuses, match reasons, error codes, storage paths, request header names, and UI labels that are reused. This improves maintainability without overengineering the prototype.

Configuration should be environment-driven:

- Backend uses `.env` and `.env.example` for API prefix, allowed CORS origins, log level, and data paths.
- Frontend uses `.env` and `.env.example` for the backend base URL and debounce interval.
- `.env` is not committed; `.env.example` is committed.

CORS should be configured explicitly so the React TypeScript frontend can call the FastAPI backend during local development. For example, `http://localhost:5173` should be allowed in development, while production origins should be controlled through environment variables.

---
## 15. Final Recommendation

For this take-home, the best architecture is a small deterministic search system:

```text
React TypeScript frontend
Python FastAPI backend
Local JSON data
In-memory search index
Explicit ranking rules
RapidFuzz only as typo fallback
No runtime LLM call
No runtime DB dependency
Strong eval harness
```

This demonstrates product judgment, engineering craft, and LLM fluency without overbuilding.

---

## 16. API Contract, Pagination, and Observability Addendum

For a small prototype, the API still follows a production-style response envelope so the frontend gets a predictable contract and the backend can be debugged easily.

### 16.1 Standard API Response Shape

All API responses use the same envelope:

```json
{
  "timestamp": "2026-05-29T10:15:30.123Z",
  "correlationId": "b7a9c7d8-2e2f-4d5a-91a0-03c7c7fdde21",
  "status": "SUCCESS",
  "message": "Airport search completed successfully",
  "data": {},
  "errors": [],
  "meta": {}
}
```

For failures:

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

### 16.2 Search Response with Limit-Based Pagination

Autocomplete search does not need full page-based pagination. The API supports `limit` and returns pagination metadata for consistency.

```http
GET /api/v1/airports/search?q=londn&limit=10
```

```json
{
  "timestamp": "2026-05-29T10:15:30.123Z",
  "correlationId": "b7a9c7d8-2e2f-4d5a-91a0-03c7c7fdde21",
  "status": "SUCCESS",
  "message": "Airport search completed successfully",
  "data": {
    "query": "londn",
    "normalizedQuery": "londn",
    "results": []
  },
  "errors": [],
  "meta": {
    "limit": 10,
    "count": 0,
    "hasMore": false,
    "latencyMs": 7
  }
}
```

The prototype intentionally avoids `page` / `offset` because airport autocomplete should return the best 5-10 ranked matches, not a long browsable list.

### 16.3 Correlation ID

Each request receives a correlation ID.

- If the frontend sends `X-Correlation-ID`, the backend preserves it.
- If not provided, the backend generates a UUID.
- The same ID is returned in the response body and `X-Correlation-ID` response header.
- Logs include the same ID for debugging.

### 16.4 Logging Strategy

The backend uses structured JSON logs for search observability.

Important fields:

```json
{
  "event": "airport_search_completed",
  "correlationId": "b7a9c7d8-2e2f-4d5a-91a0-03c7c7fdde21",
  "query": "Londn",
  "normalizedQuery": "londn",
  "resultCount": 3,
  "topResult": "London, United Kingdom",
  "topScore": 592,
  "matchReason": "FUZZY_CITY_MATCH",
  "latencyMs": 7,
  "statusCode": 200
}
```

This helps answer production questions such as:

- Which queries return no results?
- Which queries rely on fuzzy matching?
- Which aliases are missing?
- Which searches are slow?
- Which top result was shown to the user?

