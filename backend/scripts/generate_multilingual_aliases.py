"""
generate_multilingual_aliases.py — GeoNames Multilingual Alias Generator

Groups GeoNames alternateNames rows by geonameId. When a group contains
an IATA row (isolanguage == "iata"), all useful aliases in that group are
mapped to the corresponding airport in airports.json.

Pipeline:
  GeoNames .txt → parse rows → group by geonameId → find IATA rows
  → filter useful aliases → assign priority → dedupe → write JSON

Usage:
    cd backend
    python scripts/generate_multilingual_aliases.py
"""

import os
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Set, Optional, Tuple
from collections import defaultdict

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.normalizer import normalize_query

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Script detection
# ---------------------------------------------------------------------------
SCRIPT_RANGES = {
    "Thai": r"[\u0e00-\u0e7f]",
    "Han": r"[\u4e00-\u9fff]",
    "Japanese": r"[\u3040-\u30ff]",
    "Hangul": r"[\uac00-\ud7af]",
    "Arabic": r"[\u0600-\u06ff]",
    "Cyrillic": r"[\u0400-\u04ff]",
    "Devanagari": r"[\u0900-\u097f]",
    "Latin": r"[\u0000-\u024f\u1e00-\u1eff]",
}


def detect_script(text: str) -> str:
    """Detect the primary script of a text string."""
    for script_name, pattern in SCRIPT_RANGES.items():
        if re.search(pattern, text):
            # CJK + Kana → Japanese
            if script_name == "Han" and re.search(SCRIPT_RANGES["Japanese"], text):
                return "Japanese"
            return script_name
    return "Other"


# ---------------------------------------------------------------------------
# GeoNames row parser
# ---------------------------------------------------------------------------
@dataclass
class GeoNameAliasRow:
    """Structured representation of a single GeoNames alternateNames row.

    GeoNames alternateNames format (tab-separated):
      0  alternateNameId
      1  geonameId
      2  isolanguage
      3  alternateName
      4  isPreferredName   (optional, "1" or empty)
      5  isShortName       (optional, "1" or empty)
      6  isColloquial      (optional, "1" or empty)
      7  isHistoric        (optional, "1" or empty)
      8  from              (optional)
      9  to                (optional)
    """
    alternate_name_id: str
    geoname_id: str
    language: str
    name: str
    is_preferred: bool = False
    is_short: bool = False
    is_colloquial: bool = False
    is_historic: bool = False


def parse_row(line: str) -> Optional[GeoNameAliasRow]:
    """Parse a single tab-separated GeoNames alternateNames line.

    Returns None for malformed rows.
    """
    parts = line.split("\t")
    if len(parts) < 4:
        return None

    alternate_name_id = parts[0].strip()
    geoname_id = parts[1].strip()
    language = parts[2].strip()
    name = parts[3].strip()

    if not geoname_id or not name:
        return None

    def _flag(idx: int) -> bool:
        return len(parts) > idx and parts[idx].strip() == "1"

    return GeoNameAliasRow(
        alternate_name_id=alternate_name_id,
        geoname_id=geoname_id,
        language=language,
        name=name,
        is_preferred=_flag(4),
        is_short=_flag(5),
        is_colloquial=_flag(6),
        is_historic=_flag(7),
    )


def parse_and_group(filepath: str) -> Dict[str, List[GeoNameAliasRow]]:
    """Parse a GeoNames file and group rows by geonameId."""
    groups: Dict[str, List[GeoNameAliasRow]] = defaultdict(list)
    skipped = 0
    parsed = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            row = parse_row(line)
            if row is None:
                skipped += 1
                continue
            groups[row.geoname_id].append(row)
            parsed += 1

    logger.info(f"  Parsed {parsed:,} rows, skipped {skipped:,} malformed, "
                f"grouped into {len(groups):,} geonameId groups")
    return groups


# ---------------------------------------------------------------------------
# Alias filtering
# ---------------------------------------------------------------------------

# Languages that are metadata, not useful aliases
SKIP_LANGUAGES: Set[str] = {
    "link", "wkdt", "post", "unlc", "icao", "faac", "iata",
    "fr_1793", "abbr",
}

# URL pattern
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def is_useful_alias(row: GeoNameAliasRow) -> bool:
    """Return True if the row represents a useful, human-readable alias."""
    lang = row.language.lower()

    # Skip metadata languages
    if lang in SKIP_LANGUAGES:
        return False

    name = row.name.strip()

    # Skip empty
    if not name:
        return False

    # Skip URLs
    if _URL_RE.match(name):
        return False

    # Skip pure numeric
    if name.isdigit():
        return False

    # Skip very short aliases (< 2 chars) unless script warrants it
    # CJK single characters can be meaningful
    if len(name) < 2:
        script = detect_script(name)
        if script not in ("Han", "Japanese", "Hangul"):
            return False

    return True


# ---------------------------------------------------------------------------
# Priority assignment
# ---------------------------------------------------------------------------

def compute_priority(row: GeoNameAliasRow) -> int:
    """Assign priority based on alias type/flags."""
    if row.is_historic or row.is_colloquial:
        return 60
    if row.is_preferred:
        return 92
    if row.is_short:
        return 78

    lang = row.language.lower()

    # English aliases
    if lang == "en":
        return 80

    # Non-Latin / local script aliases get high priority
    script = detect_script(row.name)
    if script not in ("Latin", "Other"):
        return 90

    # Generic Latin alias (de, fr, es, etc.)
    return 80


# ---------------------------------------------------------------------------
# Airport stopword / prefix removal for alias variant generation
# ---------------------------------------------------------------------------

# Thai airport prefixes (ordered longest-first for greedy matching)
THAI_AIRPORT_PREFIXES = [
    "ท่าอากาศยานนานาชาติ",
    "สนามบินนานาชาติ",
    "ท่าอากาศยาน",
    "สนามบิน",
]

# English airport suffixes (ordered longest-first)
ENGLISH_AIRPORT_SUFFIXES = [
    "international airport",
    "airport",
    "airfield",
    "aerodrome",
]

# Arabic airport prefixes
ARABIC_AIRPORT_PREFIXES = [
    "المطار الدولي",
    "مطار دولي",
    "مطار",
]

# Hindi/Devanagari airport suffixes
HINDI_AIRPORT_SUFFIXES = [
    "अंतरराष्ट्रीय हवाई अड्डा",
    "हवाई अड्डा",
    "एयरपोर्ट",
]

# CJK airport suffixes
CJK_AIRPORT_SUFFIXES = [
    "国际机场",  # Chinese: international airport
    "國際機場",  # Traditional Chinese
    "机场",      # Chinese: airport
    "機場",      # Traditional Chinese
    "空港",      # Japanese: airport
    "공항",      # Korean: airport
]

# Generic-only aliases that should never be indexed standalone
GENERIC_AIRPORT_WORDS: Set[str] = {
    "airport", "international", "international airport",
    "airfield", "aerodrome",
    "สนามบิน", "ท่าอากาศยาน", "สนามบินนานาชาติ", "ท่าอากาศยานนานาชาติ",
    "مطار", "المطار الدولي", "مطار دولي",
    "हवाई अड्डा", "अंतरराष्ट्रीय हवाई अड्डा", "एयरपोर्ट",
    "机场", "國際機場", "国际机场", "機場", "空港", "공항",
}


def generate_alias_variants(alias: str, language: str, script: str) -> List[str]:
    """Generate alias variants by removing generic airport stopwords/prefixes.

    Returns a list of unique non-empty variants including the original.
    Generic-only results are filtered out.
    """
    variants: List[str] = [alias]  # always include original
    lang = language.lower()

    # Thai: remove prefixes
    if script == "Thai" or lang == "th":
        for prefix in THAI_AIRPORT_PREFIXES:
            if alias.startswith(prefix):
                cleaned = alias[len(prefix):].strip()
                if cleaned:
                    variants.append(cleaned)

    # English / Latin: remove suffixes (case-insensitive)
    elif script == "Latin" or lang == "en":
        alias_lower = alias.lower().strip()
        for suffix in ENGLISH_AIRPORT_SUFFIXES:
            if alias_lower.endswith(suffix):
                cleaned = alias[:len(alias) - len(suffix)].strip()
                if cleaned:
                    variants.append(cleaned)

    # Arabic: remove prefixes
    elif script == "Arabic" or lang == "ar":
        for prefix in ARABIC_AIRPORT_PREFIXES:
            if alias.startswith(prefix):
                cleaned = alias[len(prefix):].strip()
                if cleaned:
                    variants.append(cleaned)

    # Hindi/Devanagari: remove suffixes
    elif script == "Devanagari" or lang == "hi":
        for suffix in HINDI_AIRPORT_SUFFIXES:
            if alias.endswith(suffix):
                cleaned = alias[:len(alias) - len(suffix)].strip()
                if cleaned:
                    variants.append(cleaned)

    # CJK: remove suffixes
    elif script in ("Han", "Japanese", "Hangul") or lang in ("zh", "ja", "ko", "wuu", "yue"):
        for suffix in CJK_AIRPORT_SUFFIXES:
            if alias.endswith(suffix):
                cleaned = alias[:len(alias) - len(suffix)].strip()
                if cleaned:
                    variants.append(cleaned)

    # Filter out generic-only results and too-short results
    filtered: List[str] = []
    seen: Set[str] = set()
    for v in variants:
        v_stripped = v.strip()
        v_lower = v_stripped.lower() if script == "Latin" else v_stripped
        # Skip generic-only
        if v_lower in GENERIC_AIRPORT_WORDS:
            continue
        # Skip too-short (< 2 chars) unless CJK
        if len(v_stripped) < 2 and script not in ("Han", "Japanese", "Hangul"):
            continue
        if v_stripped not in seen:
            seen.add(v_stripped)
            filtered.append(v_stripped)

    return filtered


# ---------------------------------------------------------------------------
# IATA-group mapping
# ---------------------------------------------------------------------------

def extract_iata_codes(group: List[GeoNameAliasRow]) -> List[str]:
    """Extract valid IATA codes from a geonameId group."""
    codes = []
    for row in group:
        if row.language.lower() == "iata":
            code = row.name.strip().upper()
            if len(code) == 3 and code.isalpha():
                codes.append(code)
    return codes


def generate_aliases_from_group(
    group: List[GeoNameAliasRow],
    iata_codes: List[str],
    airports_by_id: Dict[str, Any],
    source_filename: str,
) -> List[Dict[str, Any]]:
    """Generate alias records for all useful aliases in an IATA-linked group.

    For each useful alias, also generates cleaned short variants by removing
    generic airport stopwords/prefixes (e.g. ท่าอากาศยาน, Airport, 机场).
    """
    aliases = []

    for iata in iata_codes:
        target_id = f"airport:{iata}"
        if target_id not in airports_by_id:
            continue

        for row in group:
            if not is_useful_alias(row):
                continue

            normalized = normalize_query(row.name).normalized
            if not normalized:
                continue

            priority = compute_priority(row)
            script = detect_script(row.name)
            lang = row.language or "unknown"

            # Original alias
            aliases.append({
                "alias": row.name,
                "normalizedAlias": normalized,
                "language": lang,
                "script": script,
                "targetType": "AIRPORT",
                "targetId": target_id,
                "priority": priority,
                "source": f"geonames:{source_filename}",
            })

            # Generate cleaned short variants
            variants = generate_alias_variants(row.name, lang, script)
            for variant in variants:
                if variant == row.name:
                    continue  # skip original, already added

                variant_normalized = normalize_query(variant).normalized
                if not variant_normalized:
                    continue

                # Variant gets slightly lower priority, never below 75
                variant_priority = max(priority - 2, 75)
                variant_script = detect_script(variant)

                aliases.append({
                    "alias": variant,
                    "normalizedAlias": variant_normalized,
                    "language": lang,
                    "script": variant_script,
                    "targetType": "AIRPORT",
                    "targetId": target_id,
                    "priority": variant_priority,
                    "source": f"geonames:{source_filename}:variant",
                })

    return aliases


# ---------------------------------------------------------------------------
# City group fallback mapping
# ---------------------------------------------------------------------------

def generate_city_group_fallback(
    group: List[GeoNameAliasRow],
    city_group_lookup: Dict[str, Dict[str, List[Dict[str, str]]]],
    country_code: str,
    source_filename: str,
) -> List[Dict[str, Any]]:
    """Conservative fallback: if no IATA row exists, try matching aliases
    to known city groups by normalized English name in the same country."""
    aliases = []
    country_lookup = city_group_lookup.get(country_code, {})
    if not country_lookup:
        return aliases

    for row in group:
        if not is_useful_alias(row):
            continue

        normalized = normalize_query(row.name).normalized
        if not normalized:
            continue

        targets = country_lookup.get(normalized)
        if targets:
            priority = compute_priority(row)
            script = detect_script(row.name)

            for t in targets:
                aliases.append({
                    "alias": row.name,
                    "normalizedAlias": normalized,
                    "language": row.language or "unknown",
                    "script": script,
                    "targetType": t["type"],
                    "targetId": t["id"],
                    "priority": priority,
                    "source": f"geonames:{source_filename}",
                })

    return aliases


# ---------------------------------------------------------------------------
# Deduplication and sorting
# ---------------------------------------------------------------------------

def dedupe_aliases(all_aliases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedupe by normalizedAlias + targetType + targetId, keeping higher priority.
    Prefer manual_seed over geonames, and original geonames over variants."""
    unique: Dict[str, Dict[str, Any]] = {}

    def _source_rank(source: str) -> int:
        """Higher rank wins in tie-breaking."""
        if source == "manual_seed":
            return 3
        if source and ":variant" in source:
            return 1
        return 2  # original geonames

    for alias in all_aliases:
        key = f"{alias['normalizedAlias']}_{alias['targetType']}_{alias['targetId']}"
        if key not in unique:
            unique[key] = alias
        else:
            existing = unique[key]
            if alias["priority"] > existing["priority"]:
                unique[key] = alias
            elif alias["priority"] == existing["priority"]:
                # At equal priority, prefer better source
                if _source_rank(alias.get("source", "")) > _source_rank(existing.get("source", "")):
                    unique[key] = alias

    # Sort deterministically
    results = sorted(
        unique.values(),
        key=lambda a: (a["script"], a["language"], a["normalizedAlias"],
                       a["targetType"], a["targetId"]),
    )
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "app", "data")

    airports_path = os.path.join(data_dir, "airports.json")
    city_groups_path = os.path.join(data_dir, "city_groups.json")
    seed_file = os.path.join(data_dir, "multilingual_aliases.seed.json")
    out_file = os.path.join(data_dir, "multilingual_aliases.json")

    # ---- Load airports ----
    with open(airports_path, "r", encoding="utf-8") as f:
        airports = json.load(f)

    airports_by_id: Dict[str, Any] = {}
    for ap in airports:
        airports_by_id[ap["id"]] = ap

    logger.info(f"Loaded {len(airports_by_id)} airports")

    # ---- Load city groups for fallback mapping ----
    with open(city_groups_path, "r", encoding="utf-8") as f:
        city_groups = json.load(f)

    # Build city group lookup: country_code -> normalized_name -> list[{type, id}]
    city_group_lookup: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    for cg in city_groups:
        cc = cg.get("countryCode", "").upper()
        if cc not in city_group_lookup:
            city_group_lookup[cc] = {}

        for name_field in ["displayName", "code", "city"]:
            val = cg.get(name_field) or ""
            if val:
                norm = normalize_query(val).normalized
                if norm:
                    if norm not in city_group_lookup[cc]:
                        city_group_lookup[cc][norm] = []
                    entry = {"type": "CITY_GROUP", "id": cg["id"]}
                    if entry not in city_group_lookup[cc][norm]:
                        city_group_lookup[cc][norm].append(entry)

        for alias in cg.get("aliases", []):
            if alias:
                norm = normalize_query(alias).normalized
                if norm:
                    if norm not in city_group_lookup[cc]:
                        city_group_lookup[cc][norm] = []
                    entry = {"type": "CITY_GROUP", "id": cg["id"]}
                    if entry not in city_group_lookup[cc][norm]:
                        city_group_lookup[cc][norm].append(entry)

    # ---- Process GeoNames files ----
    country_files = {
        "CN.txt": "CN", "JP.txt": "JP", "KR.txt": "KR", "AE.txt": "AE",
        "SA.txt": "SA", "EG.txt": "EG", "RU.txt": "RU", "UA.txt": "UA",
        "TH.txt": "TH", "AD.txt": "AD",
    }

    generated_aliases: List[Dict[str, Any]] = []
    total_rows_parsed = 0
    total_groups_processed = 0
    total_iata_linked_groups = 0
    total_aliases_generated = 0
    total_aliases_skipped = 0
    files_processed = 0

    for filename, country_code in country_files.items():
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            logger.warning(f"GeoNames file not found: {filename}")
            continue

        logger.info(f"Processing {filename} (country={country_code})...")
        files_processed += 1

        # Phase 1: Parse & group
        groups = parse_and_group(filepath)
        total_groups_processed += len(groups)

        file_rows = sum(len(rows) for rows in groups.values())
        total_rows_parsed += file_rows

        # Phase 2: Process each geonameId group
        iata_linked = 0
        file_aliases = 0
        file_skipped = 0

        for geoname_id, group in groups.items():
            iata_codes = extract_iata_codes(group)

            if iata_codes:
                # IATA-linked group — primary strategy
                iata_linked += 1
                aliases = generate_aliases_from_group(
                    group, iata_codes, airports_by_id, filename
                )
                file_aliases += len(aliases)
                file_skipped += sum(1 for row in group if not is_useful_alias(row))
                generated_aliases.extend(aliases)
            else:
                # Fallback: try city group matching (conservative)
                aliases = generate_city_group_fallback(
                    group, city_group_lookup, country_code, filename
                )
                file_aliases += len(aliases)
                generated_aliases.extend(aliases)

        total_iata_linked_groups += iata_linked
        total_aliases_generated += file_aliases
        total_aliases_skipped += file_skipped

        logger.info(f"  → IATA-linked groups: {iata_linked}, "
                    f"aliases generated: {file_aliases}")

    # ---- Merge seed aliases ----
    seeds: List[Dict[str, Any]] = []
    if os.path.exists(seed_file):
        logger.info(f"Loading seed file: {seed_file}")
        with open(seed_file, "r", encoding="utf-8") as f:
            seeds = json.load(f)
        logger.info(f"  Loaded {len(seeds)} seed aliases")

    # ---- Deduplicate ----
    all_candidates = generated_aliases + seeds
    results = dedupe_aliases(all_candidates)

    # ---- Write output ----
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # ---- Summary ----
    print()
    print("=" * 60)
    print("  GeoNames Multilingual Alias Generation — Summary")
    print("=" * 60)
    print(f"  Files processed:         {files_processed}")
    print(f"  Total rows parsed:       {total_rows_parsed:,}")
    print(f"  GeoName groups:          {total_groups_processed:,}")
    print(f"  IATA-linked groups:      {total_iata_linked_groups:,}")
    print(f"  Aliases generated:       {total_aliases_generated:,}")
    print(f"  Aliases skipped:         {total_aliases_skipped:,}")
    print(f"  Seed aliases loaded:     {len(seeds)}")
    print(f"  Final deduped count:     {len(results)}")
    print(f"  Output:                  {out_file}")
    print("=" * 60)

    # ---- Spot-check known aliases ----
    print()
    print("Spot-check known aliases:")

    spot_checks = [
        ("สุวรรณภูมิ", "airport:BKK"),
        ("ท่าอากาศยานสุวรรณภูมิ", "airport:BKK"),
        ("ภูเก็ต", "airport:HKT"),
        ("ท่าอากาศยานภูเก็ต", "airport:HKT"),
        ("กรุงเทพ", "airport:BKK"),
        ("ดอนเมือง", "airport:DMK"),
        ("北京", "city_group:beijing-cn"),
        ("東京", "city_group:tokyo-jp"),
        ("서울", "city_group:seoul-kr"),
        ("دبي", "airport:DXB"),
    ]

    for alias_name, expected_target in spot_checks:
        found = any(
            a["alias"] == alias_name and a["targetId"] == expected_target
            for a in results
        )
        # Also check normalizedAlias match for variant aliases
        if not found:
            norm_check = normalize_query(alias_name).normalized
            found = any(
                a["normalizedAlias"] == norm_check and a["targetId"] == expected_target
                for a in results
            )
        status = "✅ FOUND" if found else "❌ MISSING"
        print(f"  {status}  {alias_name!r} → {expected_target}")

    # Check if key airports exist
    for ap_id in ["airport:HKT", "airport:BKK", "airport:DMK"]:
        exists = ap_id in airports_by_id
        print(f"  {ap_id} in airports.json: {'✅ YES' if exists else '❌ NO'}")

    print()


if __name__ == "__main__":
    main()
