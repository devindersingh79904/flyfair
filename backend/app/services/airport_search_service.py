import time
import logging
import asyncio
import threading
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz
from app.services.index_builder import IndexBuilder
from app.services.normalizer import normalize_query, is_subsequence, normalized_contains
from app.services.ranker import calculate_score, deduplicate_and_sort, suppress_group_child_airport_duplicates, score_iata_exact
from app.models.search_models import SearchResult, SearchResultAirport
from app.models.response_models import SearchResponseData
from app.models.airport_models import Airport, CityGroup, RegionGroup
from app.core.constants import ResultType, MatchReason, LogEvent
from app.core.config import settings
from app.services.translation_service import TranslationService, should_try_translation


logger = logging.getLogger(__name__)

class AirportSearchService:
    def __init__(self, index: IndexBuilder, translation_service: Optional[TranslationService] = None):
        self.index = index
        self.translation_service = translation_service or TranslationService()

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

    def _search_local(self, query_str: str, limit: int) -> List[SearchResult]:
        q = normalize_query(query_str)
        candidates: List[SearchResult] = []
        query_len = len(q.normalized)

        if query_len == 0:
            return []

        self.collect_iata_exact(query_str, q, candidates)
        self.collect_city_code_exact(q, candidates)
        self.collect_alias_exact(query_str, q, candidates)
        self.collect_city_group_exact(q, candidates)
        self.collect_region_exact(q, candidates)
        self.collect_country_exact_or_alias(q, candidates)

        if query_len >= settings.PREFIX_MIN_QUERY_LENGTH:
            self.collect_iata_prefix(q, candidates)
            self.collect_city_prefix(q, candidates)
            self.collect_airport_name_prefix(q, candidates)
            self.collect_alias_prefix(q, candidates)
            self.collect_country_prefix(q, candidates)

        if settings.ENABLE_SUBSTRING_MATCH and query_len >= settings.SUBSTRING_MIN_QUERY_LENGTH:
            self.collect_substring_matches(q, candidates)

        if settings.ENABLE_SUBSEQUENCE_MATCH and query_len >= settings.SUBSEQUENCE_MIN_QUERY_LENGTH:
            self.collect_subsequence_matches(q, candidates)

        if settings.ENABLE_FUZZY_SEARCH and query_len >= settings.FUZZY_MIN_QUERY_LENGTH:
            self.collect_fuzzy_matches(q, candidates)

        # Deduplicate & Sort candidates by Score
        deduped = deduplicate_and_sort(candidates)
        
        # Suppress duplicate child airports from groups
        suppressed = suppress_group_child_airport_duplicates(deduped)
        
        return suppressed[:limit]

    def _should_call_translation_fallback(self, query_str: str, local_results: List[SearchResult]) -> bool:
        if not settings.IS_TRANSLATION_ENABLED:
            return False
        if not should_try_translation(query_str):
            return False
        if not local_results:
            return True
        top_score = local_results[0].score
        if top_score < settings.TRANSLATION_WEAK_RESULT_THRESHOLD:
            return True
        return False

    def _log_search_completed(self, query_str: str, results: List[SearchResult], latency_ms: int, translation_result: Optional[Any] = None):
        top_result_name = "None"
        top_score = 0
        match_reason_str = "None"
        if results:
            top_res = results[0]
            top_result_name = f"{top_res.displayName}, {top_res.country}"
            top_score = top_res.score
            match_reason_str = top_res.matchReason.value

        extra_log = {
            "event": LogEvent.SEARCH_COMPLETED.value,
            "query": query_str,
            "resultCount": len(results),
            "topResult": top_result_name,
            "topScore": top_score,
            "matchReason": match_reason_str,
            "latencyMs": latency_ms
        }
        if translation_result:
            extra_log.update({
                "translationFallbackUsed": True,
                "translatedQuery": translation_result.translated_text,
                "detectedLanguage": translation_result.detected_language,
                "translationProvider": translation_result.provider
            })

        logger.info(
            f"Airport search completed successfully: query='{query_str}' "
            f"resultCount={len(results)} fallbackUsed={bool(translation_result)}",
            extra=extra_log
        )

    def search(self, query_str: str, limit: int) -> tuple[SearchResponseData, int]:
        start_time = time.perf_counter()
        
        # 1. Search local index first
        local_results = self._search_local(query_str, limit)
        
        # 2. Check if we need to try translation
        if not self._should_call_translation_fallback(query_str, local_results):
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_search_completed(query_str, local_results, latency_ms)
            return SearchResponseData(results=local_results), latency_ms

        # 3. Call translation service synchronously
        translation_coro = self.translation_service.translate_to_english(query_str)
        
        # Helper runner
        def _run_sync(coro):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                result = None
                exception = None
                def target():
                    nonlocal result, exception
                    try:
                        result = asyncio.run(coro)
                    except Exception as e:
                        exception = e
                t = threading.Thread(target=target)
                t.start()
                t.join()
                if exception:
                    raise exception
                return result
            else:
                return asyncio.run(coro)

        try:
            translation_result = _run_sync(translation_coro)
        except Exception as e:
            logger.error(f"Translation fallback call failed: {str(e)}")
            translation_result = None

        
        if not translation_result or not translation_result.translated_text:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_search_completed(query_str, local_results, latency_ms)
            return SearchResponseData(results=local_results), latency_ms
            
        translated_query = translation_result.translated_text
        if normalize_query(translated_query).normalized == normalize_query(query_str).normalized:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_search_completed(query_str, local_results, latency_ms)
            return SearchResponseData(results=local_results), latency_ms

        # 4. Search again using translated English query
        translated_results = self._search_local(translated_query, limit)
        
        local_top_score = local_results[0].score if local_results else 0
        translated_top_score = translated_results[0].score if translated_results else 0
        
        if translated_top_score > local_top_score:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_search_completed(query_str, translated_results, latency_ms, translation_result)
            return SearchResponseData(
                results=translated_results,
                translationFallbackUsed=True,
                translatedQuery=translated_query,
                detectedLanguage=translation_result.detected_language,
                translationProvider=translation_result.provider
            ), latency_ms
        else:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            self._log_search_completed(query_str, local_results, latency_ms)
            return SearchResponseData(results=local_results), latency_ms

    def collect_iata_exact(self, raw_query, q, candidates):
        if len(q.upper) == 3:
            ap = self.index.airport_by_iata.get(q.upper)
            if ap:
                base_score = score_iata_exact(raw_query)
                score = calculate_score(MatchReason.IATA_EXACT, ap.commercialPriority, override_base_score=base_score)
                candidates.append(self._build_airport_result(ap, MatchReason.IATA_EXACT, score))

    def collect_city_code_exact(self, q, candidates):
        if len(q.upper) == 3:
            cg = self.index.city_group_by_code.get(q.upper)
            if cg:
                score = calculate_score(MatchReason.CITY_CODE_EXACT, cg.priority)
                candidates.append(self._build_city_group_result(cg, MatchReason.CITY_CODE_EXACT, score))

    def collect_alias_exact(self, raw_query, q, candidates):
        alias_entries = []
        # Need a dict to deduplicate entry without tuple comparison issues
        seen_entries = []
        for key in (q.lower, q.normalized):
            entries = self.index.alias_index.get(key)
            if entries:
                for entry in entries:
                    if entry not in seen_entries:
                        seen_entries.append(entry)
                        alias_entries.append((key, entry))
            
        for matched_key, entry in alias_entries:
            t_id = entry["targetId"]
            t_type = entry["targetType"]
            alias_priority = entry["priority"]
            if t_type == ResultType.AIRPORT.value:
                ap = self.index.airport_by_id.get(t_id)
                if ap:
                    if ap.iata and matched_key == ap.iata.lower():
                        # The alias matched was just the IATA code. Treat as IATA intent.
                        base_score = score_iata_exact(raw_query)
                        score = calculate_score(MatchReason.IATA_EXACT, alias_priority, override_base_score=base_score)
                        reason = MatchReason.IATA_EXACT
                    else:
                        score = calculate_score(MatchReason.ALIAS_EXACT, alias_priority)
                        reason = MatchReason.ALIAS_EXACT
                    candidates.append(self._build_airport_result(ap, reason, score))
            elif t_type == ResultType.CITY_GROUP.value:
                cg = self.index.city_group_by_id.get(t_id)
                if cg: candidates.append(self._build_city_group_result(cg, MatchReason.ALIAS_EXACT, calculate_score(MatchReason.ALIAS_EXACT, alias_priority)))
            elif t_type == ResultType.REGION_GROUP.value:
                rg = self.index.region_by_id.get(t_id)
                if rg: candidates.append(self._build_region_result(rg, MatchReason.ALIAS_EXACT, calculate_score(MatchReason.ALIAS_EXACT, alias_priority)))

    def collect_city_group_exact(self, q, candidates):
        for cg in self.index.searchable_city_groups:
            if q.normalized == cg.normalizedDisplayName or q.normalized == cg.city.lower():
                score = calculate_score(MatchReason.CITY_GROUP_EXACT, cg.priority)
                candidates.append(self._build_city_group_result(cg, MatchReason.CITY_GROUP_EXACT, score))

    def collect_region_exact(self, q, candidates):
        for rg in self.index.region_by_id.values():
            if q.normalized == rg.normalizedDisplayName or q.normalized == rg.region.lower():
                score = calculate_score(MatchReason.REGION_EXACT, rg.priority)
                candidates.append(self._build_region_result(rg, MatchReason.REGION_EXACT, score))

    def collect_country_exact_or_alias(self, q, candidates):
        matched_countries = {}
        if len(q.normalized) >= 2:
            if q.upper in self.index.countries_by_code:
                matched_countries[q.upper] = MatchReason.COUNTRY_EXACT
            if q.normalized in self.index.countries_by_name:
                matched_countries[self.index.countries_by_name[q.normalized]] = MatchReason.COUNTRY_EXACT
            if q.lower in self.index.country_alias_map:
                matched_countries[self.index.country_alias_map[q.lower]] = MatchReason.COUNTRY_ALIAS

        for c_code, reason in matched_countries.items():
            if c_code in self.index.city_groups_by_country_code:
                for cg in self.index.city_groups_by_country_code[c_code]:
                    candidates.append(self._build_city_group_result(cg, reason, calculate_score(reason, cg.priority)))
            if c_code in self.index.airports_by_country_code:
                for ap in self.index.airports_by_country_code[c_code]:
                    candidates.append(self._build_airport_result(ap, reason, calculate_score(reason, ap.commercialPriority)))

    def collect_iata_prefix(self, q, candidates):
        for ap in self.index.searchable_airports:
            if ap.normalizedIata and ap.normalizedIata.startswith(q.normalized):
                candidates.append(self._build_airport_result(ap, MatchReason.IATA_PREFIX, calculate_score(MatchReason.IATA_PREFIX, ap.commercialPriority)))
        for cg in self.index.searchable_city_groups:
            if cg.normalizedCode and cg.normalizedCode.startswith(q.normalized):
                candidates.append(self._build_city_group_result(cg, MatchReason.IATA_PREFIX, calculate_score(MatchReason.IATA_PREFIX, cg.priority)))

    def collect_city_prefix(self, q, candidates):
        for ap in self.index.searchable_airports:
            if ap.normalizedCity and ap.normalizedCity.startswith(q.normalized):
                candidates.append(self._build_airport_result(ap, MatchReason.CITY_PREFIX, calculate_score(MatchReason.CITY_PREFIX, ap.commercialPriority)))
        for cg in self.index.searchable_city_groups:
            if cg.normalizedDisplayName and cg.normalizedDisplayName.startswith(q.normalized):
                candidates.append(self._build_city_group_result(cg, MatchReason.CITY_PREFIX, calculate_score(MatchReason.CITY_PREFIX, cg.priority)))

    def collect_airport_name_prefix(self, q, candidates):
        for ap in self.index.searchable_airports:
            if ap.normalizedName and ap.normalizedName.startswith(q.normalized):
                candidates.append(self._build_airport_result(ap, MatchReason.AIRPORT_NAME_PREFIX, calculate_score(MatchReason.AIRPORT_NAME_PREFIX, ap.commercialPriority)))
        for ap in self.index.searchable_airports:
            for token in ap.normalizedTokens:
                if token.startswith(q.normalized):
                    candidates.append(self._build_airport_result(ap, MatchReason.AIRPORT_TOKEN_MATCH, calculate_score(MatchReason.AIRPORT_TOKEN_MATCH, ap.commercialPriority)))
                    break
        for cg in self.index.searchable_city_groups:
            for token in cg.normalizedTokens:
                if token.startswith(q.normalized):
                    candidates.append(self._build_city_group_result(cg, MatchReason.AIRPORT_TOKEN_MATCH, calculate_score(MatchReason.AIRPORT_TOKEN_MATCH, cg.priority)))
                    break

    def collect_alias_prefix(self, q, candidates):
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

    def collect_country_prefix(self, q, candidates):
        matched_countries = {}
        for c_name, c_code in self.index.countries_by_name.items():
            if c_name.startswith(q.normalized):
                matched_countries[c_code] = MatchReason.COUNTRY_PREFIX
            elif q.normalized in c_name.split():
                matched_countries[c_code] = MatchReason.COUNTRY_TOKEN_MATCH
        for alias, c_code in self.index.country_alias_map.items():
            if alias.startswith(q.lower):
                matched_countries[c_code] = MatchReason.COUNTRY_PREFIX
        
        for c_code, reason in matched_countries.items():
            if c_code in self.index.city_groups_by_country_code:
                for cg in self.index.city_groups_by_country_code[c_code]:
                    candidates.append(self._build_city_group_result(cg, reason, calculate_score(reason, cg.priority)))
            if c_code in self.index.airports_by_country_code:
                for ap in self.index.airports_by_country_code[c_code]:
                    candidates.append(self._build_airport_result(ap, reason, calculate_score(reason, ap.commercialPriority)))

    def collect_substring_matches(self, q, candidates):
        for ap in self.index.searchable_airports:
            if normalized_contains(q.normalized, ap.normalizedName) or normalized_contains(q.normalized, ap.normalizedCity):
                candidates.append(self._build_airport_result(ap, MatchReason.SUBSTRING_MATCH, calculate_score(MatchReason.SUBSTRING_MATCH, ap.commercialPriority)))
        for cg in self.index.searchable_city_groups:
            if normalized_contains(q.normalized, cg.normalizedDisplayName) or normalized_contains(q.normalized, cg.city.lower()):
                candidates.append(self._build_city_group_result(cg, MatchReason.SUBSTRING_MATCH, calculate_score(MatchReason.SUBSTRING_MATCH, cg.priority)))

    def collect_subsequence_matches(self, q, candidates):
        for ap in self.index.searchable_airports:
            if is_subsequence(q.normalized, ap.normalizedName) or is_subsequence(q.normalized, ap.normalizedCity):
                candidates.append(self._build_airport_result(ap, MatchReason.SUBSEQUENCE_MATCH, calculate_score(MatchReason.SUBSEQUENCE_MATCH, ap.commercialPriority)))
        for cg in self.index.searchable_city_groups:
            if is_subsequence(q.normalized, cg.normalizedDisplayName) or is_subsequence(q.normalized, cg.city.lower()):
                candidates.append(self._build_city_group_result(cg, MatchReason.SUBSEQUENCE_MATCH, calculate_score(MatchReason.SUBSEQUENCE_MATCH, cg.priority)))

    def collect_fuzzy_matches(self, q, candidates):
        for cg in self.index.searchable_city_groups:
            ratio = max(
                fuzz.ratio(q.normalized, cg.displayName.lower()),
                fuzz.ratio(q.normalized, cg.city.lower())
            )
            if ratio >= settings.FUZZY_THRESHOLD:
                score = calculate_score(MatchReason.FUZZY_CITY, cg.priority, ratio)
                candidates.append(self._build_city_group_result(cg, MatchReason.FUZZY_CITY, score))
                
        for ap in self.index.searchable_airports:
            ratio = fuzz.ratio(q.normalized, ap.city.lower())
            if ratio >= settings.FUZZY_THRESHOLD:
                score = calculate_score(MatchReason.FUZZY_CITY, ap.commercialPriority, ratio)
                candidates.append(self._build_airport_result(ap, MatchReason.FUZZY_CITY, score))
                
        for ap in self.index.searchable_airports:
            ratio = fuzz.ratio(q.normalized, ap.name.lower())
            if ratio >= settings.FUZZY_THRESHOLD:
                score = calculate_score(MatchReason.FUZZY_AIRPORT, ap.commercialPriority, ratio)
                candidates.append(self._build_airport_result(ap, MatchReason.FUZZY_AIRPORT, score))

