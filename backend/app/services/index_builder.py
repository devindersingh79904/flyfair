import os
import json
import logging
from typing import Dict, List, Any
from app.models.airport_models import Airport, CityGroup, RegionGroup, Country
from app.core.errors import DataLoadException
from app.core.constants import LogEvent, ResultType
from app.services.normalizer import normalize_query

logger = logging.getLogger(__name__)

class IndexBuilder:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        
        # Core entity indexes
        self.airport_by_iata: Dict[str, Airport] = {}
        self.airport_by_id: Dict[str, Airport] = {}
        self.city_group_by_code: Dict[str, CityGroup] = {}
        self.city_group_by_id: Dict[str, CityGroup] = {}
        self.region_by_id: Dict[str, RegionGroup] = {}
        self.countries_by_code: Dict[str, str] = {}
        self.countries_by_name: Dict[str, str] = {}
        self.airports_by_country_code: Dict[str, List[Airport]] = {}
        self.city_groups_by_country_code: Dict[str, List[CityGroup]] = {}
        
        # Country alias map
        self.country_alias_map: Dict[str, str] = {
            "uk": "GB",
            "united kingdom": "GB",
            "britain": "GB",
            "great britain": "GB",
            "usa": "US",
            "us": "US",
            "united states": "US",
            "america": "US",
            "uae": "AE",
            "united arab emirates": "AE"
        }
        
        # Alias mapping: alias_string -> List[alias_entry_dict]
        self.alias_index: Dict[str, List[Dict[str, Any]]] = {}
        
        # Search arrays for name/string fuzzy checks
        self.searchable_airports: List[Airport] = []
        self.searchable_city_groups: List[CityGroup] = []
        
        # Execute compilation
        self.load_and_build()

    def _get_file_path(self, filename: str) -> str:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            raise DataLoadException(f"Required data file missing: {filename} at {path}")
        return path

    def load_and_build(self):
        try:
            # 1. Load Countries lookup table
            countries_path = self._get_file_path("countries.json")
            with open(countries_path, "r", encoding="utf-8") as f:
                countries_data = json.load(f)
                for item in countries_data:
                    c = Country(**item)
                    self.countries_by_code[c.code.upper()] = c.name
                    self.countries_by_name[c.name.lower()] = c.code.upper()

            # 2. Load Airports
            airports_path = self._get_file_path("airports.json")
            with open(airports_path, "r", encoding="utf-8") as f:
                airports_data = json.load(f)
                for item in airports_data:
                    ap = Airport(**item)
                    
                    ap.normalizedIata = normalize_query(ap.iata).normalized if ap.iata else ""
                    ap.normalizedCity = normalize_query(ap.city).normalized if ap.city else ""
                    ap.normalizedName = normalize_query(ap.name).normalized if ap.name else ""
                    ap.normalizedAliases = [normalize_query(a).normalized for a in ap.aliases] if ap.aliases else []
                    
                    tokens = set()
                    if ap.normalizedName:
                        tokens.update(ap.normalizedName.split())
                    ap.normalizedTokens = list(tokens)

                    self.airport_by_id[ap.id] = ap
                    if ap.iata:
                        self.airport_by_iata[ap.iata.upper()] = ap
                    if ap.countryCode:
                        cc = ap.countryCode.upper()
                        if cc not in self.airports_by_country_code:
                            self.airports_by_country_code[cc] = []
                        self.airports_by_country_code[cc].append(ap)
                    self.searchable_airports.append(ap)

            # 3. Load City Groups
            city_groups_path = self._get_file_path("city_groups.json")
            with open(city_groups_path, "r", encoding="utf-8") as f:
                city_groups_data = json.load(f)
                for item in city_groups_data:
                    cg = CityGroup(**item)
                    
                    cg.normalizedCode = normalize_query(cg.code).normalized if cg.code else ""
                    cg.normalizedDisplayName = normalize_query(cg.displayName).normalized if cg.displayName else ""
                    cg.normalizedAliases = [normalize_query(a).normalized for a in cg.aliases] if cg.aliases else []
                    
                    tokens = set()
                    if cg.normalizedDisplayName:
                        tokens.update(cg.normalizedDisplayName.split())
                    cg.normalizedTokens = list(tokens)

                    self.city_group_by_id[cg.id] = cg
                    if cg.code:
                        self.city_group_by_code[cg.code.upper()] = cg
                    if cg.countryCode:
                        cc = cg.countryCode.upper()
                        if cc not in self.city_groups_by_country_code:
                            self.city_groups_by_country_code[cc] = []
                        self.city_groups_by_country_code[cc].append(cg)
                    self.searchable_city_groups.append(cg)

            # 4. Load Regions
            # Load from regions_lookup.json if it exists, otherwise fallback to regions.json
            try:
                regions_path = self._get_file_path("regions_lookup.json")
            except DataLoadException:
                regions_path = self._get_file_path("regions.json")
                
            with open(regions_path, "r", encoding="utf-8") as f:
                regions_data = json.load(f)
                for item in regions_data:
                    # Depending on raw region format or curated format
                    # Ensure compatibility with both by filtering keys if needed
                    # but RegionGroup model might fail if keys are missing
                    # Since regions_lookup.json has 'localCode' but not 'region'
                    pass
            # Wait, the previous logic used regions.json. 
            # If the user says "keep existing curated regions.json unchanged", we should load `regions.json`!
            regions_path = self._get_file_path("regions.json")
            with open(regions_path, "r", encoding="utf-8") as f:
                regions_data = json.load(f)
                for item in regions_data:
                    rg = RegionGroup(**item)
                    
                    rg.normalizedDisplayName = normalize_query(rg.displayName).normalized if rg.displayName else ""
                    rg.normalizedAliases = [normalize_query(a).normalized for a in rg.aliases] if rg.aliases else []
                    
                    tokens = set()
                    if rg.normalizedDisplayName:
                        tokens.update(rg.normalizedDisplayName.split())
                    rg.normalizedTokens = list(tokens)
                    
                    self.region_by_id[rg.id] = rg

            # 5. Load Curated Aliases
            aliases_path = self._get_file_path("aliases.json")
            with open(aliases_path, "r", encoding="utf-8") as f:
                aliases_data = json.load(f)
                for item in aliases_data:
                    alias_str = item["alias"].strip().lower()
                    normalized_alias = item["normalizedAlias"].strip().lower()
                    
                    alias_entry = {
                        "targetType": item["targetType"],
                        "targetId": item["targetId"],
                        "priority": item["priority"]
                    }
                    
                    for key in (alias_str, normalized_alias):
                        if not key:
                            continue
                        if key not in self.alias_index:
                            self.alias_index[key] = []
                        if alias_entry not in self.alias_index[key]:
                            self.alias_index[key].append(alias_entry)

            # 6. Inject Generated Aliases from Entities
            def inject_aliases(aliases_list, target_id, target_type, priority):
                for a in aliases_list:
                    nq = normalize_query(a)
                    keys = set([nq.lower, nq.normalized])
                    entry = {"targetType": target_type, "targetId": target_id, "priority": priority}
                    for k in keys:
                        if k:
                            if k not in self.alias_index:
                                self.alias_index[k] = []
                            if entry not in self.alias_index[k]:
                                self.alias_index[k].append(entry)

            for ap in self.searchable_airports:
                inject_aliases(ap.aliases, ap.id, ResultType.AIRPORT.value, ap.commercialPriority)
                
            for cg in self.searchable_city_groups:
                inject_aliases(cg.aliases, cg.id, ResultType.CITY_GROUP.value, cg.priority)
                
            for rg in self.region_by_id.values():
                inject_aliases(rg.aliases, rg.id, ResultType.REGION_GROUP.value, rg.priority)

            logger.info(
                "In-memory indexes populated successfully.",
                extra={
                    "event": LogEvent.DATA_LOAD_SUCCESS.value,
                    "airportsCount": len(self.airport_by_id),
                    "cityGroupsCount": len(self.city_group_by_id),
                    "regionsCount": len(self.region_by_id),
                    "aliasesCount": len(self.alias_index)
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to load search data indexes: {str(e)}",
                extra={"event": LogEvent.DATA_LOAD_FAILURE.value}
            )
            raise DataLoadException(f"Index building failed: {str(e)}")
