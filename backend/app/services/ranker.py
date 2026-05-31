from typing import List, Dict, Any
from app.models.search_models import SearchResult
from app.core.constants import BASE_SCORES, MatchReason

def calculate_score(
    base_reason: MatchReason,
    priority: int,
    similarity_ratio: float = 100.0
) -> int:
    """
    Calculate search result score.
    score = baseScore + fuzzyScoreAdjustment + priorityBoost
    - For exact match tiers, fuzzyScoreAdjustment is 0.
    - For fuzzy match tiers, adjustment is calculated as negative penalty: (similarity_ratio - 100) * 2
    """
    base_score = BASE_SCORES.get(base_reason, 0)
    
    # Calculate fuzzy penalty if it's a fuzzy matching tier
    if base_reason in (MatchReason.FUZZY_CITY, MatchReason.FUZZY_AIRPORT):
        fuzzy_adjustment = int((similarity_ratio - 100.0) * 2.0)
    else:
        fuzzy_adjustment = 0
        
    priority_boost = min(10, int(priority / 10))
    score = base_score + fuzzy_adjustment + priority_boost
    return score

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
