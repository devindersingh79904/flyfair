# Fly Fairly Airport Search

A full-stack product-minded airport search implementation designed for high relevance, typo tolerance, and intuitive grouping (e.g. searching "London" returns all London airports under a unified city group).

## Features
- **In-Memory Search**: Lightning-fast, robust search using RapidFuzz for fuzzy string matching. No external database required.
- **Product-Minded Relevance**: Prioritizes major hubs, exact IATA/City Code matches, and curated aliases (e.g., CJK support, native accents).
- **Country and Region Search**: Queries like "United Kingdom", "UK", "UAE", or "United" gracefully fall back to matching the country and serving the top relevant commercial airports and city groups.
- **Multilingual Support & Fallback**: Fully deterministic, offline multi-language support (English, Chinese, Japanese, Thai, Hindi, Arabic, Korean, and Latin diacritics) powered by static `multilingual_aliases.json`. If no strong local result is found for a non-English/non-Latin query, the engine can optionally fall back to the Google Cloud Translation API to translate the query into English and search again.
- **Hierarchical Groups & Duplicate Suppression**: Searches for a city (like Tokyo or London) or a region return a grouped parent row with child airports nested below it. Child airports are intrinsically suppressed from appearing again as separate top-level rows to ensure a clean UI. Direct airport searches still return exact airports normally.
- **One-Time Data Generation**: Ships with a Python script to compile static JSON lists directly from OurAirports CSV data. Includes ~9,000 valid commercial airports.

## Prerequisites
- Python 3.12+ (if running locally)
- Node.js 20+ (if running locally)
- Docker & Docker Compose (for containerized deployment)

## Environment Variables
The application relies on `.env` files for configuration. You should create them from the provided `.env.example` templates.

**`backend/.env.example`**:
```env
APP_NAME=Fly Fairly Airport Search API
APP_ENV=local
APP_HOST=0.0.0.0
APP_PORT=8000
API_PREFIX=/api/v1

# CORS Origins
# For local development:
BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# For quick demo only:
# BACKEND_CORS_ORIGINS=*
# When "*" is used, backend automatically disables CORS credentials.

# For production:
# BACKEND_CORS_ORIGINS=https://flyfair.devinderpanesar.com
LOG_LEVEL=INFO


# Search behavior
ENABLE_FUZZY_SEARCH=true
ENABLE_SUBSTRING_MATCH=true
ENABLE_SUBSEQUENCE_MATCH=true
FUZZY_MIN_QUERY_LENGTH=4
FUZZY_THRESHOLD=82
PREFIX_MIN_QUERY_LENGTH=1
SUBSTRING_MIN_QUERY_LENGTH=2
SUBSEQUENCE_MIN_QUERY_LENGTH=3
MAX_SEARCH_RESULTS=20
DEFAULT_SEARCH_LIMIT=10

# Translation fallback
ENABLE_TRANSLATION_FALLBACK=false
TRANSLATION_PROVIDER=google
GOOGLE_TRANSLATE_API_KEY=
GOOGLE_TRANSLATE_TARGET_LANGUAGE=en
TRANSLATION_MIN_QUERY_LENGTH=2
TRANSLATION_MAX_QUERY_LENGTH=80
TRANSLATION_WEAK_RESULT_THRESHOLD=650
TRANSLATION_CACHE_MAX_SIZE=1000
TRANSLATION_REQUEST_TIMEOUT_SECONDS=3
```

**`frontend/.env.example`**:
```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_SHOW_DEBUG_RANKING=false
```
> **Note**: In Docker, `VITE_API_BASE_URL` uses `localhost:8000` because the user's browser makes requests from the host machine directly to the mapped port, and cannot resolve the internal Docker service name `backend`.

## Setup and Execution Instructions (Local)

### 1. Data Generation (Offline)
The project comes with generated data. If you want to regenerate it from the raw CSVs (`airports.csv`, `countries.csv`, `regions.csv` in `backend/raw_data/`):
```bash
make generate-data
```

To regenerate multilingual aliases from GeoNames alternateNames files (e.g. `TH.txt`, `CN.txt`, etc. in `backend/app/data/`):
```bash
cd backend && .venv/bin/python scripts/generate_multilingual_aliases.py
```
This groups GeoNames rows by `geonameId`, finds IATA codes within each group, and maps all useful non-Latin aliases to the matching airport.

### 2. Backend Setup
Install dependencies and run tests:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python scripts/run_eval.py
```

### 3. Frontend Setup
Install dependencies and build:
```bash
cd frontend
npm install
npm run build
```

### 4. Running the App Locally
Run these in separate terminals:
```bash
make dev-backend
make dev-frontend
```

## Setup and Execution Instructions (Docker)

To run the full stack via Docker Compose:
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build -d
```

### Validation
- **Frontend**: http://localhost:5173
- **Backend Health**: http://localhost:8000/api/v1/health
- **Swagger Docs**: http://localhost:8000/docs

## Examples

### Country Search Examples
Try querying the following strings to see the country fallback mechanism:
- `"United Kingdom"` → Yields the London City Group (LHR, LGW, etc.)
- `"UK"` → Alias for United Kingdom, yields London City Group.
- `"UAE"` → Alias for United Arab Emirates, yields DXB (Dubai).
- `"United"` → Matches United Kingdom, United States, and United Arab Emirates, yielding the top airports and city groups from these countries.
- `"goa"` → Natural destination query; yields Goa India City Group.
- `"GOA"` → Explicit IATA intent query; yields Genoa Cristoforo Colombo Airport (GOA).
- `"lon"` / `"LON"` → Protected major city code; always yields London City Group.
- `"LHR"` → Explicit IATA intent; yields London Heathrow.

### Multilingual Search Examples
The multilingual alias pipeline groups GeoNames alternateNames by `geonameId`. If a group contains an IATA row, all useful aliases are linked to the matching airport:
- `"ภูเก็ต"` → Thai alias for Phuket; yields `airport:HKT` (Phuket International Airport).
- `"ท่าอากาศยานภูเก็ต"` → Thai airport name for Phuket; yields `airport:HKT`.
- `"กรุงเทพ"` → Thai for Bangkok; yields `airport:BKK` (Suvarnabhumi Airport).
- `"東京"` → Chinese/Japanese for Tokyo; yields Tokyo City Group.
- `"서울"` → Korean for Seoul; yields Seoul City Group.
- `"دبي"` → Arabic for Dubai; yields `airport:DXB`.
- `"São Paulo"` / `"Sao Paulo"` → Accent-folded; both yield São Paulo City Group.

## Google Translate Fallback

The backend supports an optional runtime translation fallback:
1. **Local Search First**: The search engine always searches local offline aliases first. No translation API is called if a strong local match (score >= `TRANSLATION_WEAK_RESULT_THRESHOLD`, default `650`) is found.
2. **Detection & Filter**: Only non-English/non-Latin queries (containing Thai, Han/CJK, Japanese Hiragana/Katakana, Hangul, Arabic, Cyrillic, or Devanagari characters) with length >= `TRANSLATION_MIN_QUERY_LENGTH` (default `2`) are eligible for translation. English, ASCII, and IATA codes (e.g. `LON`, `LHR`, `Goa`) are never translated.
3. **Execution**: If eligible, the query is translated to English via the Google Cloud Translation API and searched again.
4. **Caching**: Successful translation results are cached in an in-memory LRU cache (capped at `TRANSLATION_CACHE_MAX_SIZE`, default `1000`) to minimize external API costs.
5. **Robustness**: If the Google Translate API is down, fails, or credentials are missing, search falls back gracefully without crashing or returning errors.

To enable this feature, configure these variables in `backend/.env`:
```env
ENABLE_TRANSLATION_FALLBACK=true
TRANSLATION_PROVIDER=google
GOOGLE_TRANSLATE_API_KEY=<your-google-cloud-api-key>
GOOGLE_TRANSLATE_TARGET_LANGUAGE=en
TRANSLATION_MIN_QUERY_LENGTH=2
TRANSLATION_MAX_QUERY_LENGTH=80
TRANSLATION_WEAK_RESULT_THRESHOLD=650
TRANSLATION_CACHE_MAX_SIZE=1000
TRANSLATION_REQUEST_TIMEOUT_SECONDS=3
```

## CORS Configuration

Proper Cross-Origin Resource Sharing (CORS) is enforced by the backend:
- **Local development:** The frontend usually runs on `http://localhost:5173`. Add this explicitly to `BACKEND_CORS_ORIGINS`.
- **Production frontend:** You must explicitly whitelist your deployed frontend origin (e.g. `https://flyfair.devinderpanesar.com`) in `BACKEND_CORS_ORIGINS`. This keeps the API secure and allows the browser to send credentials if needed.
- **Demo / Wildcard:** `BACKEND_CORS_ORIGINS=*` is supported for quick demos. Note that when the backend detects `*`, it automatically sets `allow_credentials=False` because modern browsers reject wildcard origins when credentials (like cookies or auth headers) are included.

If you are updating these variables in a deployed environment like EasyPanel, you must redeploy or restart the backend container for the environment variables to take effect.

You can verify the backend is correctly returning CORS preflight headers with cURL:

```bash
curl -i -X OPTIONS "https://aiagentstudio-flyfair-backend.ia8ype.easypanel.host/api/v1/airports/search?q=lon&limit=10" \
  -H "Origin: https://flyfair.devinderpanesar.com" \
  -H "Access-Control-Request-Method: GET"
```

You should see `access-control-allow-origin` in the HTTP response headers.

## EasyPanel Deployment Notes

When deploying on EasyPanel, you should adjust the environment settings in the backend service configuration.

**Recommended production environment:**
```env
APP_ENV=production
BACKEND_CORS_ORIGINS=https://flyfair.devinderpanesar.com
LOG_LEVEL=INFO
```

**Demo wildcard environment:**
```env
BACKEND_CORS_ORIGINS=*
```

*Note: After changing the environment variables in the EasyPanel UI, you must restart or redeploy the backend service so the changes take effect in the application container.*
