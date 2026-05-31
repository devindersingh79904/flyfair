#!/usr/bin/env python3
"""
run_eval.py — Fly Fairly Airport Search Evaluation Script

Exercises the 25 required evaluation cases against the in-process search
service. Run from the backend/ directory:

    cd backend
    python scripts/run_eval.py

Exit code 0 = all cases passed.
Exit code 1 = one or more cases failed.
"""

import sys
import os

# Make sure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.index_builder import IndexBuilder
from app.services.airport_search_service import AirportSearchService
from app.core.constants import ResultType

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "data"
)

# ---------------------------------------------------------------------------
# Evaluation cases — all queries verified against the bundled dataset.
#
# Each tuple: (description, query, expected_top_id | None, optional_check_fn | None)
# When expected_top_id is None, check_fn must be provided.
# ---------------------------------------------------------------------------
EVAL_CASES = [
    # --- IATA Exact (Layer 1) ---
    ("IATA exact - LHR", "LHR", "airport:LHR", None),
    ("IATA exact lowercase - lhr", "lhr", "airport:LHR", None),
    ("IATA exact - DXB", "DXB", "airport:DXB", None),
    ("IATA exact - MUC", "MUC", "airport:MUC", None),
    # --- City Code Exact (Layer 2) ---
    ("City code - LON", "LON", "city_group:london-gb", None),
    ("City code - TYO", "TYO", "city_group:tokyo-jp", None),
    ("City code - SEL", "SEL", "city_group:seoul-kr", None),
    # --- Alias Exact — multilingual (Layer 3) ---
    ("CJK alias - 東京 → Tokyo city group", "東京", "city_group:tokyo-jp", None),
    ("CJK alias - 北京 → Beijing city group", "北京", "city_group:beijing-cn", None),
    ("Korean alias - 서울 → Seoul city group", "서울", "city_group:seoul-kr", None),
    ("Arabic alias - دبي → DXB", "دبي", "airport:DXB", None),
    # --- Accent / Unicode folding ---
    ("Accent fold - Sao Paulo → city group", "Sao Paulo", "city_group:sao-paulo-br", None),
    ("Native accent - São Paulo → city group", "São Paulo", "city_group:sao-paulo-br", None),
    ("Umlaut native - München → MUC", "München", "airport:MUC", None),
    ("Umlaut fold - Munchen → MUC", "Munchen", "airport:MUC", None),
    # --- City Group exact (Layer 4) ---
    ("City group - London UK first", "London", "city_group:london-gb", None),
    ("City group - Tokyo", "Tokyo", "city_group:tokyo-jp", None),
    ("City group - Rome → city group over individual airport", "Rome", "city_group:rome-it", None),
    # --- Region (Layer 5) ---
    ("Region - Florida returns region group", "Florida", None,
     lambda r: len(r) > 0 and r[0].type == ResultType.REGION_GROUP and r[0].id == "region:us-fl"),
    ("Region - Hawaii returns region group", "Hawaii", None,
     lambda r: len(r) > 0 and r[0].type == ResultType.REGION_GROUP and r[0].id == "region:us-hi"),
    # --- Airport name exact (Layer 6) ---
    ("Airport name - Heathrow → LHR", "Heathrow", "airport:LHR", None),
    ("Airport name - Gatwick → LGW", "Gatwick", "airport:LGW", None),
    # --- Fuzzy typo tolerance (Layer 8/9) ---
    ("Typo - Londun → London GB city group", "Londun", "city_group:london-gb", None),
    ("Typo - Tokio → Tokyo city group", "Tokio", "city_group:tokyo-jp", None),
    ("Typo - Dubay → DXB", "Dubay", "airport:DXB", None),
    # --- Short Query Autocomplete (Prefix / Token) ---
    ("Short Query - ix returns IX* airports", "ix", None, lambda r: len(r) > 0 and any([ap.iata.startswith("IX") for r2 in r for ap in r2.airports if ap.iata])),
    ("Short Query - lhr returns LHR exact", "lhr", "airport:LHR", None),
    ("Short Query - lon returns london city group", "lon", "city_group:london-gb", None),
    ("Short Query - dub includes DXB", "dub", None, lambda r: len(r) > 0 and any(["DXB" in [ap.iata for ap in r2.airports] for r2 in r])),
    # --- Country Queries ---
    ("Country - United Kingdom -> london-gb", "United Kingdom", "city_group:london-gb", None),
    ("Country - UK -> london-gb", "UK", "city_group:london-gb", None),
    ("Country - UAE -> DXB", "UAE", None, lambda r: len(r) > 0 and any([c.id == "airport:DXB" for c in r])),
    ("Country - United Arab Emirates -> DXB", "United Arab Emirates", "airport:DXB", None),
    ("Country - USA -> non-empty US results", "USA", None, lambda r: len(r) > 0 and any([c.countryCode == "US" for c in r])),
    ("Country - United -> matches GB/US/AE", "United", None, lambda r: len(r) > 0 and any([c.countryCode in ["GB", "US", "AE"] for c in r])),
]

assert len(EVAL_CASES) == 35, f"Expected 35 cases, got {len(EVAL_CASES)}"


def run_eval():
    print("=" * 68)
    print("  Fly Fairly Airport Search — Evaluation Suite (29 cases)")
    print(f"  Data directory: {DATA_DIR}")
    print("=" * 68)

    index = IndexBuilder(DATA_DIR)
    service = AirportSearchService(index)

    passed = 0
    failed = 0

    for i, (desc, query, expected_id, check_fn) in enumerate(EVAL_CASES, start=1):
        response_data, _ = service.search(query, limit=10)
        results = response_data.results

        actual_top = results[0].id if results else "NO_RESULTS"
        actual_top_name = results[0].displayName if results else "—"
        actual_score = results[0].score if results else 0

        if expected_id is not None:
            ok = actual_top == expected_id
        elif check_fn is not None:
            ok = check_fn(results)
        else:
            ok = len(results) > 0

        status = "✅ PASS" if ok else "❌ FAIL"
        if ok:
            passed += 1
        else:
            failed += 1

        line = (
            f"[{i:02d}] {status}  {desc!r:50s}  "
            f"query={query!r:15s}  top={actual_top!r} ({actual_top_name})"
        )
        if not ok and expected_id:
            line += f"  EXPECTED={expected_id!r}"
        print(line)

    print()
    print("=" * 68)
    print(f"  RESULTS: {passed}/{len(EVAL_CASES)} passed, {failed} failed")
    print("=" * 68)

    return failed == 0


if __name__ == "__main__":
    success = run_eval()
    sys.exit(0 if success else 1)
