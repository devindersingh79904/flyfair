import time
import logging
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz
from app.services.index_builder import IndexBuilder
from app.services.normalizer import normalize_query
from app.services.ranker import calculate_score, deduplicate_and_sort
from app.models.search_models import SearchResult, SearchResultAirport
from app.models.response_models import SearchResponseData
from app.models.airport_models import Airport, CityGroup, RegionGroup
from app.core.constants import ResultType, MatchReason, LogEvent

logger = logging.getLogger(__name__)

class AirportSearchService:
    def __init__(self, index: IndexBuilder):
        self.index = index

    def _map_airport_to_summary(self, ap: Airport) -> SearchResultAirport:
        return SearchResultAirport(
            id=ap.id,
            iata=ap.iata,
            name=ap.name,
            city=ap.city,
            region=ap.region,
            country=ap.country,
            countryCode=ap.countryCode
        )

    def _build_airport_result(self, ap: Airport, reason: MatchReason, score: int) -> SearchResult:
        return SearchResult(
            id=ap.id,
            type=ResultType.AIRPORT,
            displayName=ap.name,
            city=ap.city,
            region=ap.region,
            country=ap.country,
            countryCode=ap.countryCode,
            score=score,
            matchReason=reason,
            airports=[self._map_airport_to_summary(ap)]
        )

    def _build_city_group_result(self, cg: CityGroup, reason: MatchReason, score: int) -> SearchResult:
        airports = []
        for iata in cg.airportIatas:
            ap = self.index.airport_by_iata.get(iata.upper())
            if ap:
                airports.append(self._map_airport_to_summary(ap))
        return SearchResult(
            id=cg.id,
            type=ResultType.CITY_GROUP,
            code=cg.code,
            displayName=cg.displayName,
            city=cg.city,
            region=cg.region,
            country=cg.country,
            countryCode=cg.countryCode,
            score=score,
            matchReason=reason,
            airports=airports
        )

    def _build_region_result(self, rg: RegionGroup, reason: MatchReason, score: int) -> SearchResult:
        airports = []
        for iata in rg.airportIatas:
            ap = self.index.airport_by_iata.get(iata.upper())
            if ap:
                airports.append(self._map_airport_to_summary(ap))
        return SearchResult(
            id=rg.id,
            type=ResultType.REGION_GROUP,
            displayName=rg.displayName,
            city=None,
            region=rg.region,
            country=rg.country,
            countryCode=rg.countryCode,
            score=score,
            matchReason=reason,
            airports=airports
        )

    def search(self, query_str: str, limit: int) -> SearchResponseData:
        start_time = time.perf_counter()
        
        q = normalize_query(query_str)
        candidates: List[SearchResult] = []
        query_len = len(q.normalized)

        if query_len == 0:
            return SearchResponseData(results=[])

        # Exact Matches (Run only if query length >= 3)
        if query_len >= 3:
            # IATA Exact
            if len(q.upper) == 3:
                ap = self.index.airport_by_iata.get(q.upper)
                if ap:
                    score = calculate_score(MatchReason.IATA_EXACT, ap.commercialPriority)
                    candidates.append(self._build_airport_result(ap, MatchReason.IATA_EXACT, score))

            # City Code Exact
            if len(q.upper) == 3:
                cg = self.index.city_group_by_code.get(q.upper)
                if cg:
                    score = calculate_score(MatchReason.CITY_CODE_EXACT, cg.priority)
                    candidates.append(self._build_city_group_result(cg, MatchReason.CITY_CODE_EXACT, score))

            # Alias Exact
            alias_entries = []
            for key in (q.lower, q.normalized):
                entries = self.index.alias_index.get(key)
                if entries:
                    for entry in entries:
                        if entry not in alias_entries:
                            alias_entries.append(entry)
                
            for entry in alias_entries:
                t_id = entry["targetId"]
                t_type = entry["targetType"]
                alias_priority = entry["priority"]
                if t_type == ResultType.AIRPORT.value:
                    ap = self.index.airport_by_id.get(t_id)
                    if ap:
                        score = calculate_score(MatchReason.ALIAS_EXACT, alias_priority)
                        candidates.append(self._build_airport_result(ap, MatchReason.ALIAS_EXACT, score))
                elif t_type == ResultType.CITY_GROUP.value:
                    cg = self.index.city_group_by_id.get(t_id)
                    if cg:
                        score = calculate_score(MatchReason.ALIAS_EXACT, alias_priority)
                        candidates.append(self._build_city_group_result(cg, MatchReason.ALIAS_EXACT, score))
                elif t_type == ResultType.REGION_GROUP.value:
                    rg = self.index.region_by_id.get(t_id)
                    if rg:
                        score = calculate_score(MatchReason.ALIAS_EXACT, alias_priority)
                        candidates.append(self._build_region_result(rg, MatchReason.ALIAS_EXACT, score))

            # City Group Exact
            for cg in self.index.searchable_city_groups:
                if q.normalized == cg.normalizedDisplayName or q.normalized == cg.city.lower():
                    score = calculate_score(MatchReason.CITY_GROUP_EXACT, cg.priority)
                    candidates.append(self._build_city_group_result(cg, MatchReason.CITY_GROUP_EXACT, score))

            # Region Exact
            for rg in self.index.region_by_id.values():
                if q.normalized == rg.normalizedDisplayName or q.normalized == rg.region.lower():
                    score = calculate_score(MatchReason.REGION_EXACT, rg.priority)
                    candidates.append(self._build_region_result(rg, MatchReason.REGION_EXACT, score))

            # Airport Name Exact
            for ap in self.index.searchable_airports:
                if q.normalized == ap.normalizedName:
                    score = calculate_score(MatchReason.AIRPORT_NAME_EXACT, ap.commercialPriority)
                    candidates.append(self._build_airport_result(ap, MatchReason.AIRPORT_NAME_EXACT, score))

            # City Exact
            for ap in self.index.searchable_airports:
                if q.normalized == ap.normalizedCity:
                    score = calculate_score(MatchReason.CITY_EXACT, ap.commercialPriority)
                    candidates.append(self._build_airport_result(ap, MatchReason.CITY_EXACT, score))

        # Country Matches
        matched_countries: Dict[str, MatchReason] = {}
        
        # Exact / Alias
        if query_len >= 2:
            if q.upper in self.index.countries_by_code:
                matched_countries[q.upper] = MatchReason.COUNTRY_EXACT
            if q.normalized in self.index.countries_by_name:
                matched_countries[self.index.countries_by_name[q.normalized]] = MatchReason.COUNTRY_EXACT
            if q.lower in self.index.country_alias_map:
                matched_countries[self.index.country_alias_map[q.lower]] = MatchReason.COUNTRY_ALIAS

        # Prefix
        if query_len >= 2:
            for c_name, c_code in self.index.countries_by_name.items():
                if c_name.startswith(q.normalized) and c_code not in matched_countries:
                    matched_countries[c_code] = MatchReason.COUNTRY_PREFIX
                elif query_len >= 3 and q.normalized in c_name.split() and c_code not in matched_countries:
                    matched_countries[c_code] = MatchReason.COUNTRY_TOKEN_MATCH
            for alias, c_code in self.index.country_alias_map.items():
                if alias.startswith(q.lower) and c_code not in matched_countries:
                    matched_countries[c_code] = MatchReason.COUNTRY_PREFIX

        for c_code, reason in matched_countries.items():
            if c_code in self.index.city_groups_by_country_code:
                for cg in self.index.city_groups_by_country_code[c_code]:
                    score = calculate_score(reason, cg.priority)
                    candidates.append(self._build_city_group_result(cg, reason, score))
            if c_code in self.index.airports_by_country_code:
                for ap in self.index.airports_by_country_code[c_code]:
                    score = calculate_score(reason, ap.commercialPriority)
                    candidates.append(self._build_airport_result(ap, reason, score))

        # Prefix Matches
        for ap in self.index.searchable_airports:
            # IATA Prefix
            if ap.normalizedIata and ap.normalizedIata.startswith(q.normalized):
                score = calculate_score(MatchReason.IATA_PREFIX, ap.commercialPriority)
                candidates.append(self._build_airport_result(ap, MatchReason.IATA_PREFIX, score))
            
            # City Prefix
            if ap.normalizedCity and ap.normalizedCity.startswith(q.normalized):
                score = calculate_score(MatchReason.CITY_PREFIX, ap.commercialPriority)
                candidates.append(self._build_airport_result(ap, MatchReason.CITY_PREFIX, score))
                
            # Airport Name Prefix
            if ap.normalizedName and ap.normalizedName.startswith(q.normalized):
                score = calculate_score(MatchReason.AIRPORT_NAME_PREFIX, ap.commercialPriority)
                candidates.append(self._build_airport_result(ap, MatchReason.AIRPORT_NAME_PREFIX, score))
                
            # Airport Token Match (query_len >= 2)
            if query_len >= 2:
                for token in ap.normalizedTokens:
                    if token.startswith(q.normalized):
                        score = calculate_score(MatchReason.AIRPORT_TOKEN_MATCH, ap.commercialPriority)
                        candidates.append(self._build_airport_result(ap, MatchReason.AIRPORT_TOKEN_MATCH, score))
                        break

        for cg in self.index.searchable_city_groups:
            if cg.normalizedCode and cg.normalizedCode.startswith(q.normalized):
                score = calculate_score(MatchReason.IATA_PREFIX, cg.priority)
                candidates.append(self._build_city_group_result(cg, MatchReason.IATA_PREFIX, score))
                
            if cg.normalizedDisplayName and cg.normalizedDisplayName.startswith(q.normalized):
                score = calculate_score(MatchReason.CITY_PREFIX, cg.priority)
                candidates.append(self._build_city_group_result(cg, MatchReason.CITY_PREFIX, score))
                
            if query_len >= 2:
                for token in cg.normalizedTokens:
                    if token.startswith(q.normalized):
                        score = calculate_score(MatchReason.AIRPORT_TOKEN_MATCH, cg.priority)
                        candidates.append(self._build_city_group_result(cg, MatchReason.AIRPORT_TOKEN_MATCH, score))
                        break

        # Alias Prefix
        for alias_key, entries in self.index.alias_index.items():
            if alias_key.startswith(q.normalized) or alias_key.startswith(q.lower):
                for entry in entries:
                    t_id = entry["targetId"]
                    t_type = entry["targetType"]
                    alias_priority = entry["priority"]
                    score = calculate_score(MatchReason.ALIAS_PREFIX, alias_priority)
                    
                    if t_type == ResultType.AIRPORT.value:
                        ap = self.index.airport_by_id.get(t_id)
                        if ap: candidates.append(self._build_airport_result(ap, MatchReason.ALIAS_PREFIX, score))
                    elif t_type == ResultType.CITY_GROUP.value:
                        cg = self.index.city_group_by_id.get(t_id)
                        if cg: candidates.append(self._build_city_group_result(cg, MatchReason.ALIAS_PREFIX, score))
                    elif t_type == ResultType.REGION_GROUP.value:
                        rg = self.index.region_by_id.get(t_id)
                        if rg: candidates.append(self._build_region_result(rg, MatchReason.ALIAS_PREFIX, score))

        # Fuzzy matching (Run only if query length >= 4)
        if query_len >= 4:
            for cg in self.index.searchable_city_groups:
                ratio = max(
                    fuzz.ratio(q.normalized, cg.displayName.lower()),
                    fuzz.ratio(q.normalized, cg.city.lower())
                )
                if ratio >= 70.0:
                    score = calculate_score(MatchReason.FUZZY_CITY, cg.priority, ratio)
                    candidates.append(self._build_city_group_result(cg, MatchReason.FUZZY_CITY, score))
                    
            for ap in self.index.searchable_airports:
                ratio = fuzz.ratio(q.normalized, ap.city.lower())
                if ratio >= 70.0:
                    score = calculate_score(MatchReason.FUZZY_CITY, ap.commercialPriority, ratio)
                    candidates.append(self._build_airport_result(ap, MatchReason.FUZZY_CITY, score))
                    
            for ap in self.index.searchable_airports:
                ratio = fuzz.ratio(q.normalized, ap.name.lower())
                if ratio >= 70.0:
                    score = calculate_score(MatchReason.FUZZY_AIRPORT, ap.commercialPriority, ratio)
                    candidates.append(self._build_airport_result(ap, MatchReason.FUZZY_AIRPORT, score))

        # Deduplicate & Sort candidates by Score
        deduped = deduplicate_and_sort(candidates)
        sliced = deduped[:limit]
        
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        top_result_name = "None"
        top_score = 0
        match_reason_str = "None"
        if sliced:
            top_res = sliced[0]
            top_result_name = f"{top_res.displayName}, {top_res.country}"
            top_score = top_res.score
            match_reason_str = top_res.matchReason.value

        logger.info(
            f"Airport search completed successfully: query='{query_str}' resultCount={len(sliced)}",
            extra={
                "event": LogEvent.SEARCH_COMPLETED.value,
                "query": query_str,
                "normalizedQuery": q.normalized,
                "resultCount": len(sliced),
                "topResult": top_result_name,
                "topScore": top_score,
                "matchReason": match_reason_str,
                "latencyMs": latency_ms
            }
        )

        return SearchResponseData(results=sliced), latency_ms
