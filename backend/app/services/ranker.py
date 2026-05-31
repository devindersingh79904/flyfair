from typing import List, Dict, Any
from app.models.search_models import SearchResult
from app.core.constants import BASE_SCORES, MatchReason, ResultType, PROTECTED_CITY_CODES, IATA_NATURAL_PENALTY

def calculate_score(
    base_reason: MatchReason,
    priority: int,
    similarity_ratio: float = 100.0,
    override_base_score: int = None
) -> int:
    """
    Calculate search result score.
    score = baseScore + fuzzyScoreAdjustment + priorityBoost
    - For exact match tiers, fuzzyScoreAdjustment is 0.
    - For fuzzy match tiers, adjustment is calculated as negative penalty: (similarity_ratio - 100) * 2
    """
    base_score = override_base_score if override_base_score is not None else BASE_SCORES.get(base_reason, 0)
    
    # Calculate fuzzy penalty if it's a fuzzy matching tier
    if base_reason in (MatchReason.FUZZY_CITY, MatchReason.FUZZY_AIRPORT):
        fuzzy_adjustment = int((similarity_ratio - 100.0) * 2.0)
    else:
        fuzzy_adjustment = 0
        
    priority_boost = min(10, int(priority / 10))
    score = base_score + fuzzy_adjustment + priority_boost
    return score

def is_explicit_iata_query(raw_query: str) -> bool:
    """Check if the query is an exact 3-letter uppercase string, indicating explicit IATA intent."""
    stripped = raw_query.strip()
    return len(stripped) == 3 and stripped.isalpha() and stripped.isupper()

def score_iata_exact(raw_query: str) -> int:
    """Return IATA_EXACT score, applying a penalty if it's a natural/lowercase query or protected city."""
    base = BASE_SCORES[MatchReason.IATA_EXACT]
    return base if should_iata_exact_win_over_city_group(raw_query) else base - IATA_NATURAL_PENALTY

def should_iata_exact_win_over_city_group(raw_query: str) -> bool:
    """
    Returns True if an exact IATA match should trump a city group match.
    Only explicit uppercase queries not in PROTECTED_CITY_CODES win.
    """
    if not is_explicit_iata_query(raw_query):
        return False
    if raw_query.strip().upper() in PROTECTED_CITY_CODES:
        return False
    return True

def deduplicate_and_sort(candidates: List[SearchResult]) -> List[SearchResult]:
    """
    Deduplicate a list of search results by their ID, keeping the entry with the highest score.
    Sorts descending by score, and resolves ties deterministically using display name.
    """
    best_results: Dict[str, SearchResult] = {}
    
    for item in candidates:
        existing = best_results.get(item.id)
        if not existing or item.score > existing.score:
            best_results[item.id] = item
            
    # Convert to list and sort
    sorted_results = list(best_results.values())
    type_rank = {"CITY_GROUP": 1, "REGION_GROUP": 2, "AIRPORT": 3}
    sorted_results.sort(key=lambda x: (-x.score, type_rank.get(x.type.value, 4), x.displayName, x.id))
    
    return sorted_results

def suppress_group_child_airport_duplicates(results: List[SearchResult]) -> List[SearchResult]:
    """
    Suppresses top-level AIRPORT results if they are already nested inside a 
    REGION_GROUP or CITY_GROUP present in the same result set.
    """
    child_iatas = set()

    for result in results:
        if result.type in (ResultType.CITY_GROUP, ResultType.REGION_GROUP):
            for airport in result.airports:
                if airport.iata:
                    child_iatas.add(airport.iata.upper())

    filtered = []
    for result in results:
        if result.type == ResultType.AIRPORT:
            airport_iata = None
            if result.airports:
                airport_iata = result.airports[0].iata
            elif getattr(result, 'code', None):
                airport_iata = getattr(result, 'code')

            if airport_iata and airport_iata.upper() in child_iatas:
                continue

        filtered.append(result)

    return filtered
