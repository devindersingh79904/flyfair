import os
import json
import logging
import re
from typing import Dict, Any, List, Set, Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.normalizer import normalize_query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRIPT_RANGES = {
    "Han": r"[\u4e00-\u9fff]",
    "Japanese": r"[\u3040-\u30ff]",
    "Hangul": r"[\uac00-\ud7af]",
    "Arabic": r"[\u0600-\u06ff]",
    "Cyrillic": r"[\u0400-\u04ff]",
    "Thai": r"[\u0e00-\u0e7f]",
    "Devanagari": r"[\u0900-\u097f]",
    "Latin": r"[\u0000-\u024f\u1e00-\u1eff]"
}

def detect_script(text: str) -> str:
    for script_name, pattern in SCRIPT_RANGES.items():
        if re.search(pattern, text):
            if script_name == "Han" and re.search(SCRIPT_RANGES["Japanese"], text):
                return "Japanese"
            return script_name
    return "Other"

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "app", "data")
    
    airports_path = os.path.join(data_dir, "airports.json")
    city_groups_path = os.path.join(data_dir, "city_groups.json")
    seed_file = os.path.join(data_dir, "multilingual_aliases.seed.json")
    out_file = os.path.join(data_dir, "multilingual_aliases.json")
    
    with open(airports_path, "r", encoding="utf-8") as f:
        airports = json.load(f)
        
    with open(city_groups_path, "r", encoding="utf-8") as f:
        city_groups = json.load(f)
        
    # Build O(1) lookup dictionary
    # country_code -> normalized_name -> list of target dicts
    lookup_map: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    
    def add_lookup(cc: str, norm: str, t_type: str, t_id: str):
        if not norm: return
        if cc not in lookup_map:
            lookup_map[cc] = {}
        if norm not in lookup_map[cc]:
            lookup_map[cc][norm] = []
        lookup_map[cc][norm].append({"type": t_type, "id": t_id})
        
    for ap in airports:
        cc = ap.get("countryCode", "").upper()
        norm_city = normalize_query(ap.get("city") or "").normalized
        norm_name = normalize_query(ap.get("name") or "").normalized
        norm_iata = normalize_query(ap.get("iata") or "").normalized
        norm_aliases = [normalize_query(a or "").normalized for a in ap.get("aliases", []) if a]
        
        for n in [norm_city, norm_name, norm_iata] + norm_aliases:
            add_lookup(cc, n, "AIRPORT", ap["id"])
            
    for cg in city_groups:
        cc = cg.get("countryCode", "").upper()
        norm_display = normalize_query(cg.get("displayName") or "").normalized
        norm_code = normalize_query(cg.get("code") or "").normalized
        norm_aliases = [normalize_query(a or "").normalized for a in cg.get("aliases", []) if a]
        
        for n in [norm_display, norm_code] + norm_aliases:
            add_lookup(cc, n, "CITY_GROUP", cg["id"])

    country_files = {
        "CN.txt": "CN", "JP.txt": "JP", "KR.txt": "KR", "AE.txt": "AE", 
        "SA.txt": "SA", "EG.txt": "EG", "RU.txt": "RU", "UA.txt": "UA", 
        "TH.txt": "TH", "AD.txt": "AD"
    }

    generated_aliases = []

    for filename, country_code in country_files.items():
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            logger.warning(f"GeoNames file not found: {filename}")
            continue
            
        logger.info(f"Processing {filename}...")
        
        country_lookup = lookup_map.get(country_code, {})
        
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split("\t")
                if len(parts) < 4:
                    continue
                
                isolanguage = parts[2].strip()
                alternate_name = parts[3].strip()
                if not alternate_name: continue
                
                norm_name = normalize_query(alternate_name).normalized
                if not norm_name: continue
                
                targets = country_lookup.get(norm_name)
                if targets:
                    script = detect_script(alternate_name)
                    # To avoid duplicate combinations per line, we keep track
                    seen = set()
                    for t in targets:
                        key = f"{t['type']}_{t['id']}"
                        if key not in seen:
                            generated_aliases.append({
                                "alias": alternate_name,
                                "normalizedAlias": norm_name,
                                "language": isolanguage or "unknown",
                                "script": script,
                                "targetType": t["type"],
                                "targetId": t["id"],
                                "priority": 88,
                                "source": f"geonames:{filename}"
                            })
                            seen.add(key)

    seeds = []
    if os.path.exists(seed_file):
        logger.info(f"Loading seed file from {seed_file}")
        with open(seed_file, "r", encoding="utf-8") as f:
            seeds = json.load(f)
            
    unique_aliases: Dict[str, Dict[str, Any]] = {}
    all_candidates = generated_aliases + seeds
    
    for alias in all_candidates:
        key = f"{alias['normalizedAlias']}_{alias['targetType']}_{alias['targetId']}"
        if key not in unique_aliases:
            unique_aliases[key] = alias
        else:
            existing = unique_aliases[key]
            if alias["priority"] > existing["priority"]:
                unique_aliases[key] = alias
            elif alias["priority"] == existing["priority"]:
                if alias["source"] == "manual_seed":
                    unique_aliases[key] = alias

    results = list(unique_aliases.values())
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Generated {len(results)} multilingual aliases to {out_file}")

if __name__ == "__main__":
    main()
