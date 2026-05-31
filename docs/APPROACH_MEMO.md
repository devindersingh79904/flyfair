# Approach Memo - Fly Fairly Airport Search

## Data Source and Cleaning
For the prototype, the dataset is intentionally curated from provided JSON files generated from OurAirports data and enriched with aliases, city groups, regions, and multilingual mappings. It is not a complete production global airport database.

In a production environment, this would be backed by a daily ETL pipeline processing raw CSV files from OurAirports, enriching them with multilingual labels from GeoNames, and applying automated pruning rules based on commercial schedule data (to filter out private runways and helipads).

## Search Approach Chosen
We selected a **layered, deterministic, in-memory indexing search engine** with a fuzzy-matching fallback using `RapidFuzz` for typo correction:
1. **Layered exact matching**:
   - `IATA_EXACT` (1000)
   - `CITY_CODE_EXACT` (950)
   - `ALIAS_EXACT` (900)
   - `CITY_GROUP_EXACT` (850)
   - `REGION_EXACT` (800)
   - `AIRPORT_NAME_EXACT` (750)
   - `CITY_EXACT` (700)
2. **Layered fuzzy fallback**:
   - `FUZZY_CITY` (500)
   - `FUZZY_AIRPORT` (450)
   
Deterministic base scores prevent fuzzy noise from overriding exact matches (e.g. searching "Bali" returns DPS instead of Balikpapan).

## LLM/Tool Usage & Prompt Iteration Log
During development, we used automated tools for folder scaffolding, data copying, code generation, and test execution. The prompt guidelines mandated:
- Strict validation checks on limits (`limit > 20` returning 422 errors instead of silent clamping).
- Unified standard envelopes for all responses (casing `status` as "SUCCESS" or "ERROR").
- Observability metadata (latency in milliseconds, Correlation ID logging).
These constraints were translated into code, ensuring clean separation between index, ranking, normalization, and API layers.

## Build vs Buy vs Fake Decisions
- **Build (In-Memory Indexer & Normalizer)**: Built from scratch to guarantee deterministic scoring and zero database dependencies.
- **Buy (RapidFuzz & Unidecode)**: Imported established Python libraries for edit distance calculation and accent folding.
- **Fake (Data Files)**: Used static JSON files representing a production database slice to keep the setup light.

## Where LLM was Wrong and How Caught
1. **Indentation Error**: An accidental indentation offset in `exception_handlers.py` caused compilation failures. Caught by the test collection loader during `pytest` initialization.
2. **Lifespan Event Missing in API Tests**: The TestClient was initially instantiated globally without a context manager, causing lifespan setup to be skipped. Consequently, `app.state.search_service` remained uninitialized. Caught by API test failures and resolved by wrapping the TestClient in a pytest fixture with a context manager.
3. **Accent Folding Alias Logic Bug**: The alias lookup originally fell back to `q.normalized` *only* if `q.lower` returned no matches. However, the query `"São Paulo"` matched some alias entries (GRU/CGH airports) but missed the city group mapped to the folded key `"sao paulo"`. Caught by the `test_search_accent_folding` service test and resolved by searching both keys and combining the results.

## Production Evaluation Metrics
To scale the prototype, we would monitor:
- **P95/P99 Latency**: Ensuring autocomplete queries complete in <15ms.
- **Zero-Result Query Rate**: Analyzing queries returning no matches to identify missing aliases or multilingual scripts.
- **Click-Through / Selection Rate**: Logging which search result card is selected to refine priority weights.
- **Abandonment Rate**: Tracking queries where the dropdown was dismissed without a selection.

## Automated Evaluation Suite (`run_eval.py`)
A dedicated `backend/scripts/run_eval.py` script runs all 25 evaluation cases in-process (no HTTP server required) and exits with code 0 (pass) or 1 (fail). This script is wired into:
- **Local dev**: `make eval` from the repo root.
- **CI**: GitHub Actions runs it on every push/PR alongside `pytest`.

This ensures that ranking contract regressions are caught immediately — before any code lands on `main`.

## CI Pipeline (GitHub Actions)
`.github/workflows/ci.yml` runs two parallel jobs on each push:
1. **`backend-tests`**: Installs Python 3.11, runs `pytest tests/ -v`, then `python scripts/run_eval.py`.
2. **`frontend-build`**: Installs Node 20, runs `npx tsc --noEmit` TypeScript check, then `npm run build`.

Both must pass for a PR to be mergeable.

## Where LLM Was Wrong and How Caught

1. **Indentation Error**: An accidental indentation offset in `exception_handlers.py` caused compilation failures. Caught by the test collection loader during `pytest` initialization.

2. **Lifespan Event Missing in API Tests**: The TestClient was initially instantiated globally without a context manager, causing lifespan setup to be skipped. Consequently, `app.state.search_service` remained uninitialized. Caught by API test failures and resolved by wrapping the TestClient in a pytest fixture with a context manager.

3. **Accent Folding Alias Logic Bug**: The alias lookup originally fell back to `q.normalized` *only* if `q.lower` returned no matches. However, the query `"São Paulo"` matched some alias entries (GRU/CGH airports) but missed the city group mapped to the folded key `"sao paulo"`. Caught by the `test_search_accent_folding` service test and resolved by searching both keys and combining the results.

4. **Alias Priority Not Used in Scoring (Critical)**: The initial ALIAS_EXACT scoring used the entity's own `commercialPriority` (from the airport/city-group record) instead of the alias entry's `priority` field. This meant that even though the 北京 alias had a city-group entry with priority 99, the search service scored it using the city group's `priority=96`, which lost to the PEK airport's `commercialPriority=98`. The fix: `calculate_score(MatchReason.ALIAS_EXACT, alias_priority)` — using the alias row's priority. This is the key lever for curators to control city-group-vs-airport preference per-alias, discovered via the evaluation script revealing 北京 → PEK instead of Beijing city group.

5. **서울 Missing from aliases.json**: `city_groups.json` contained `"서울"` in its `aliases` array, but the index builder only reads `aliases.json` for alias lookups, not city group embedded aliases. The alias lookup on Layer 3 therefore never found `서울`. Discovered by running the eval script and observing `서울 → airport:ICN` instead of the expected `city_group:seoul-kr`. Fixed by adding explicit `서울` entries to `aliases.json` with priority 99.

6. **Middleware ContextVar Reset Before Completion Log**: The initial middleware used a single `try/finally` block. The `finally` (which reset the ContextVar) ran before the post-response log statement, causing `correlationId` to be `null` in the completion log. Fixed with a nested `try-finally` pattern: the inner `try` catches the call_next response, the completion log fires while the ContextVar is still set, and the outer `finally` resets it.

## Future Production Improvements
- **Automated OurAirports Ingestion**: Replacing static files with automated daily ingestion scripts.
- **GeoNames Multilingual Enrichment**: Expanding the alias dataset for minor non-Latin scripts.
- **Search Regression Suite in CI**: Running automated checks on the top 1000 search queries on every build to prevent ranking regression.
- **Alias Priority Tooling**: An internal admin UI to let data curators adjust alias priorities and immediately see the ranking impact in the eval suite.


### May 2026 Update: Data Generation Pipeline
A one-time Python generation script (`backend/scripts/generate_airport_data.py`) was introduced to process raw OurAirports CSV data. Instead of maintaining a small curated JSON file or parsing large CSVs at runtime, this script compiles ~9,000 valid commercial airports with pre-computed aliases, folded search texts, and priorities into static JSON arrays (`airports.json`, `regions_lookup.json`, `countries.json`). This ensures the `IndexBuilder` starts instantly and fuzzy matching scales efficiently.
