# Evaluation Cases — Fly Fairly Airport Search

All 25 evaluation cases are verified by `backend/scripts/run_eval.py` and run automatically in CI.

Run locally:
```bash
cd backend
python scripts/run_eval.py
```

---

## Case Table

| # | Query | Expected Top Result ID | Type | Airports | What It Validates |
|---|---|---|---|---|---|
| 01 | `LHR` | `airport:LHR` | AIRPORT | LHR | IATA exact match (uppercase) |
| 02 | `lhr` | `airport:LHR` | AIRPORT | LHR | IATA exact match (lowercase — case insensitive) |
| 03 | `DXB` | `airport:DXB` | AIRPORT | DXB | IATA exact match |
| 04 | `MUC` | `airport:MUC` | AIRPORT | MUC | IATA exact match |
| 05 | `LON` | `city_group:london-gb` | CITY_GROUP | LHR, LGW, STN, LCY, LTN | City code exact match |
| 06 | `TYO` | `city_group:tokyo-jp` | CITY_GROUP | HND, NRT | City code exact match |
| 07 | `SEL` | `city_group:seoul-kr` | CITY_GROUP | ICN, GMP | City code exact match |
| 08 | `東京` | `city_group:tokyo-jp` | CITY_GROUP | HND, NRT | CJK Japanese script alias → city group wins over individual airports |
| 09 | `北京` | `city_group:beijing-cn` | CITY_GROUP | PEK, PKX | CJK Chinese script alias → city group wins over PEK (alias priority 99 > 98) |
| 10 | `서울` | `city_group:seoul-kr` | CITY_GROUP | ICN, GMP | Korean Hangul alias → city group wins over ICN (alias priority 99 > 98) |
| 11 | `دبي` | `airport:DXB` | AIRPORT | DXB | Arabic script alias lookup |
| 12 | `Sao Paulo` | `city_group:sao-paulo-br` | CITY_GROUP | GRU, CGH, VCP | ASCII accent fold → city group wins (alias priority 96 > GRU@94) |
| 13 | `São Paulo` | `city_group:sao-paulo-br` | CITY_GROUP | GRU, CGH, VCP | Native accented alias → city group |
| 14 | `München` | `airport:MUC` | AIRPORT | MUC | Native German umlaut alias |
| 15 | `Munchen` | `airport:MUC` | AIRPORT | MUC | Accent-stripped umlaut fold via normalizer |
| 16 | `London` | `city_group:london-gb` | CITY_GROUP | LHR, LGW, STN, LCY, LTN | City group disambiguation: UK (priority 100) > Canada (45) > Kentucky (25) |
| 17 | `Tokyo` | `city_group:tokyo-jp` | CITY_GROUP | HND, NRT | City group by name |
| 18 | `Rome` | `city_group:rome-it` | CITY_GROUP | FCO, CIA | City group over individual airport (alias priority 94 > FCO@92) |
| 19 | `Florida` | `region:us-fl` | REGION_GROUP | MIA, MCO, TPA, FLL, JAX, PBI | Region group over La Florida Chile (LSC) airport alias |
| 20 | `Hawaii` | `region:us-hi` | REGION_GROUP | HNL, OGG, KOA, LIH | Region group match |
| 21 | `Heathrow` | `airport:LHR` | AIRPORT | LHR | Airport name exact match |
| 22 | `Gatwick` | `airport:LGW` | AIRPORT | LGW | Airport name exact match |
| 23 | `Londun` | `city_group:london-gb` | CITY_GROUP | LHR, LGW, STN, LCY, LTN | Fuzzy typo tolerance (RapidFuzz fallback, ratio ≥ 70) |
| 24 | `Tokio` | `city_group:tokyo-jp` | CITY_GROUP | HND, NRT | Fuzzy typo tolerance |
| 25 | `Dubay` | `airport:DXB` | AIRPORT | DXB | Fuzzy typo tolerance for Arabic city name |
| 26 | `ix` | `airport:IXB` (first) | AIRPORT | IX* airports | Short query autocomplete (prefix) |
| 27 | `lhr` | `airport:LHR` | AIRPORT | LHR | Short query exact autocomplete |
| 28 | `lon` | `city_group:london-gb` | CITY_GROUP | LON | Short query city group autocomplete |
| 29 | `dub` | `airport:DUB` | AIRPORT | DUB | Short query autocomplete (includes DXB) |
| 30 | `United Kingdom` | `city_group:london-gb` | CITY_GROUP | LON | Country query fallback |
| 31 | `UK` | `city_group:london-gb` | CITY_GROUP | LON | Country alias fallback |
| 32 | `UAE` | `airport:DXB` (within top) | AIRPORT | DXB | Country alias fallback (asserted via check_fn) |
| 33 | `United Arab Emirates` | `airport:DXB` | AIRPORT | DXB | Country name match |
| 34 | `USA` | Non-empty US results | AIRPORT/CITY | | Country alias returning top region results |
| 35 | `United` | Matches GB/US/AE | AIRPORT/CITY | | Country prefix match yielding multiple countries |

---

## Ranking Score Contract

Scores are deterministic. The formula is:

```
score = BASE_SCORE[matchReason] + aliasPriority + fuzzyAdjustment
```

| Match Reason | Base Score |
|---|---|
| `IATA_EXACT` | 1000 |
| `ALIAS_EXACT` | 980 |
| `CITY_CODE_EXACT` | 950 |
| `CITY_GROUP_EXACT` | 930 |
| `REGION_EXACT` | 900 |
| `COUNTRY_EXACT` | 870 |
| `COUNTRY_ALIAS` | 860 |
| `IATA_PREFIX` | 850 |
| `ALIAS_PREFIX` | 840 |
| `COUNTRY_PREFIX` | 830 |
| `CITY_PREFIX` | 820 |
| `AIRPORT_NAME_PREFIX` | 780 |
| `COUNTRY_TOKEN_MATCH` | 760 |
| `AIRPORT_TOKEN_MATCH` | 720 |
| `AIRPORT_NAME_EXACT` | 700 |
| `CITY_EXACT` | 680 |
| `FUZZY_CITY` | 500 |
| `FUZZY_AIRPORT` | 450 |

For fuzzy tiers: `fuzzyAdjustment = (similarityRatio - 100) * 2` (penalty from 0 to -60 for 70-100% matches).

---

## Key Design Decisions Validated

1. **Alias priority drives ALIAS_EXACT ranking** — the score uses the alias entry's own `priority` field, not the entity's `commercialPriority`. This lets data curators control city-group-vs-airport preference per-alias without touching code.
2. **City groups always win when their alias priority is set higher** — CJK/Korean aliases have priority 99, ensuring city group beats individual airport at priority 98.
3. **Fuzzy runs on all tiers** — exact matches have scores 700-1000+; fuzzy has 440-560. Exact always wins. Fuzzy only surfaces when no exact match exists.
4. **Region aliases beat similarly-named airports** — Florida region group has score 800+priority > La Florida Chile airport score.
