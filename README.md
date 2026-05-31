# Fly Fairly Airport Search

A full-stack product-minded airport search implementation designed for high relevance, typo tolerance, and intuitive grouping (e.g. searching "London" returns all London airports under a unified city group).

## Features
- **In-Memory Search**: Lightning-fast, robust search using RapidFuzz for fuzzy string matching. No external database required.
- **Product-Minded Relevance**: Prioritizes major hubs, exact IATA/City Code matches, and curated aliases (e.g., CJK support, native accents).
- **Country and Region Search**: Queries like "United Kingdom", "UK", "UAE", or "United" gracefully fall back to matching the country and serving the top relevant commercial airports and city groups.
- **Multilingual Support**: Fully deterministic, offline multi-language support (English, Chinese, Japanese, Hindi, Arabic, Korean, and Latin diacritics) powered by static `multilingual_aliases.json`. No runtime translation APIs required!
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
BACKEND_CORS_ORIGINS=*
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
