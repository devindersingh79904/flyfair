# Approach Memo: Multilingual Search Strategy

We have purposefully avoided integrating an external runtime translation API (e.g., Google Translate API) or embedding heavy local NLP translation models for multilingual search.

### Why No Runtime Translation API?
1. **Latency:** Real-time translation APIs introduce unpredictable network latency (200ms+), which violates our goal of a sub-50ms autocomplete experience.
2. **Cost and Dependency:** Third-party APIs introduce operational overhead, rate limits, and recurring costs.
3. **Determinism:** Translation models might translate "Bali" or "Delhi" differently depending on context. For a search product, we require deterministic alias matching (e.g., 北京 -> Beijing).

### Our Strategy: Offline Aliases
We use `multilingual_aliases.json` to store static mappings of common foreign names (Chinese, Japanese, Hindi, Arabic, Korean) to their exact internal IDs (`airport:DXB`, `city_group:tokyo-jp`). The search engine treats these native scripts as exact strings or prefixes without trying to transliterate them to English. This is fast, deterministic, and requires no external calls.

### Future Roadmap: Scalable Enrichment
For production scaling, rather than maintaining aliases manually, the data generation pipeline should ingest the **GeoNames `alternateNames` dump**. This provides comprehensive offline names for cities and airports across 100+ languages. A custom admin tool could also allow editors to add manual aliases, which are then compiled into the static JSON during deployment, maintaining lightning-fast search analytics and performance.
