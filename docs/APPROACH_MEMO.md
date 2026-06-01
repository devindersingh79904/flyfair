# Approach Memo: Hybrid Multilingual Search Strategy

We use a hybrid approach that combines fast, deterministic offline alias indexes with a runtime translation fallback (Google Translate API) to achieve the best balance of cost, performance, and coverage.

### Why a Hybrid Strategy?

1. **Performance & Latency**: Running translation APIs on every search request is too slow for real-time autocomplete (adding 100–300ms latency). The offline alias index resolves the vast majority of native script searches (e.g., `東京`, `서울`, `دبي`) instantly (sub-5ms) with zero API overhead.
2. **Operational Cost**: Caching translation results and limiting queries to non-English/non-Latin queries prevents unnecessary API costs.
3. **Determinism vs. Long-Tail Coverage**: While offline aliases are 100% deterministic and free, they cannot reasonably cover all possible long-tail local scripts. The Google Translate fallback provides maximum coverage for long-tail multilingual city and airport names that are not locally indexed.

### Core Architecture

- **Primary Lookup (Offline Aliases)**: First, search local indexes (`aliases.json`, `multilingual_aliases.json`, and generated aliases).
- **Fallback Trigger**: If results are empty or weak (top score < `TRANSLATION_WEAK_RESULT_THRESHOLD`), and the query is in a non-Latin script (Thai, Han/CJK, Cyrillic, Arabic, Korean, or Devanagari), trigger the translation fallback.
- **In-Memory LRU Cache**: Store successful translations in an in-memory LRU cache to prevent duplicate external network requests.
- **Graceful Failure**: If the API call fails or is misconfigured, return the local search result/no results gracefully without crashing the runtime.

