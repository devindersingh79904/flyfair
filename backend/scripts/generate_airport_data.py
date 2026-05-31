import csv
import json
import os
import shutil
from datetime import datetime, timezone
import unidecode

RAW_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "raw_data")
APP_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "data")

MAJOR_HUBS = {
    "JFK", "LHR", "DXB", "SIN", "HND", "NRT", "CDG", "AMS", "FRA", 
    "DOH", "DEL", "BOM", "BLR", "SFO", "LAX", "ORD", "ATL", "PEK", 
    "PKX", "ICN", "GRU"
}

VALID_TYPES = {"large_airport", "medium_airport", "small_airport"}
INVALID_TYPES = {"closed", "heliport", "seaplane_base", "balloonport"}

def backup_file(filepath: str):
    if os.path.exists(filepath):
        shutil.copy2(filepath, filepath + ".bak")

def load_csv(filename: str):
    filepath = os.path.join(RAW_DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

def generate_countries():
    rows = load_csv("countries.csv")
    countries = []
    for row in rows:
        countries.append({
            "code": row["code"],
            "name": row["name"]
        })
    countries.sort(key=lambda x: x["code"])
    
    out_path = os.path.join(APP_DATA_DIR, "countries.json")
    backup_file(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(countries, f, indent=2, ensure_ascii=False)
        
    return countries

def generate_regions():
    rows = load_csv("regions.csv")
    regions = []
    for row in rows:
        regions.append({
            "code": row["code"],
            "localCode": row["local_code"],
            "name": row["name"],
            "countryCode": row["iso_country"]
        })
    regions.sort(key=lambda x: x["code"])
    
    # We output to regions_lookup.json to avoid overwriting curated regions.json
    out_path = os.path.join(APP_DATA_DIR, "regions_lookup.json")
    backup_file(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(regions, f, indent=2, ensure_ascii=False)
        
    return regions

def clean_alias(val: str) -> str:
    if not val:
        return ""
    return " ".join(val.strip().lower().split())

def generate_aliases(iata, city, name, country):
    raw_aliases = [iata, city, name]
    if city:
        raw_aliases.append(unidecode.unidecode(city))
    if name:
        raw_aliases.append(unidecode.unidecode(name))
        
    aliases = set()
    country_lower = country.lower() if country else ""
    
    for a in raw_aliases:
        clean_a = clean_alias(a)
        if clean_a and clean_a != country_lower:
            aliases.add(clean_a)
            
    return sorted(list(aliases))

def generate_airports(country_map, region_map):
    rows = load_csv("airports.csv")
    airports = []
    
    for row in rows:
        iata = row.get("iata_code", "").strip().upper()
        if not iata:
            continue
            
        atype = row.get("type", "")
        if atype not in VALID_TYPES or atype in INVALID_TYPES:
            continue
            
        icao = row.get("gps_code", "").strip() or row.get("ident", "").strip()
        country_code = row.get("iso_country", "").strip()
        region_code = row.get("iso_region", "").strip()
        
        country = country_map.get(country_code, country_code)
        region = region_map.get(region_code, region_code)
        city = row.get("municipality", "").strip()
        name = row.get("name", "").strip()
        
        try:
            lat = float(row.get("latitude_deg", 0))
            lon = float(row.get("longitude_deg", 0))
        except ValueError:
            lat, lon = 0.0, 0.0
            
        priority = 40
        if atype == "large_airport":
            priority = 90
        elif atype == "medium_airport":
            priority = 70
            
        if iata in MAJOR_HUBS:
            priority = min(100, priority + 10)
            
        aliases = generate_aliases(iata, city, name, country)
        
        ap = {
            "id": f"airport:{iata}",
            "iata": iata,
            "icao": icao,
            "name": name,
            "city": city,
            "region": region,
            "regionCode": region_code,
            "country": country,
            "countryCode": country_code,
            "type": atype,
            "latitude": lat,
            "longitude": lon,
            "commercialPriority": priority,
            "aliases": aliases
        }
        airports.append(ap)
        
    airports.sort(key=lambda x: (x["country"], x["city"], x["iata"]))
    
    out_path = os.path.join(APP_DATA_DIR, "airports.json")
    backup_file(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(airports, f, indent=2, ensure_ascii=False)
        
    return len(rows), len(airports)

def generate_manifest(raw_count, generated_count, countries_count, regions_count):
    manifest = {
        "source": "OurAirports CSV",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rawFiles": {
            "airports": "backend/raw_data/airports.csv",
            "countries": "backend/raw_data/countries.csv",
            "regions": "backend/raw_data/regions.csv"
        },
        "filters": {
            "includedTypes": list(VALID_TYPES),
            "excludedTypes": list(INVALID_TYPES),
            "requiresIata": True
        },
        "counts": {
            "rawAirports": raw_count,
            "generatedAirports": generated_count,
            "countries": countries_count,
            "regions": regions_count
        },
        "notes": [
            "Generated airport index includes all OurAirports rows with IATA codes for large, medium, and small airports.",
            "Curated aliases, city groups, and region groups are maintained separately for product-specific search behavior."
        ]
    }
    out_path = os.path.join(APP_DATA_DIR, "source_manifest.json")
    backup_file(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

def main():
    print("Generating countries...")
    countries = generate_countries()
    country_map = {c["code"]: c["name"] for c in countries}
    
    print("Generating regions...")
    regions = generate_regions()
    region_map = {r["code"]: r["name"] for r in regions}
    
    print("Generating airports...")
    raw_count, generated_count = generate_airports(country_map, region_map)
    
    print("Generating manifest...")
    generate_manifest(raw_count, generated_count, len(countries), len(regions))
    
    print(f"Done! Generated {generated_count} airports.")

if __name__ == "__main__":
    main()
