from app.services.ranker import calculate_score, deduplicate_and_sort
from app.models.search_models import SearchResult
from app.core.constants import MatchReason, ResultType

def test_calculate_score():
    # Exact IATA match
    score = calculate_score(MatchReason.IATA_EXACT, priority=90)
    assert score == 1009

    # Exact City match
    score = calculate_score(MatchReason.CITY_EXACT, priority=50)
    assert score == 685

    # Fuzzy match with penalty
    # base is 500, priority 20, similarity 90 => penalty is (90-100)*2 = -20
    # score = 500 - 20 + 20 = 500
    score = calculate_score(MatchReason.FUZZY_CITY, priority=20, similarity_ratio=90.0)
    assert score == 482

def test_deduplicate_and_sort():
    # Create mock search results with duplicate IDs
    item1 = SearchResult(
        id="airport:MIA",
        type=ResultType.AIRPORT,
        displayName="Miami International Airport",
        country="United States",
        countryCode="US",
        score=750,
        matchReason=MatchReason.CITY_EXACT,
        airports=[]
    )
    
    # Same ID but higher score
    item2 = SearchResult(
        id="airport:MIA",
        type=ResultType.AIRPORT,
        displayName="Miami International Airport",
        country="United States",
        countryCode="US",
        score=1009,
        matchReason=MatchReason.IATA_EXACT,
        airports=[]
    )

    # Different ID but lower score
    item3 = SearchResult(
        id="airport:TPA",
        type=ResultType.AIRPORT,
        displayName="Tampa International Airport",
        country="United States",
        countryCode="US",
        score=820,
        matchReason=MatchReason.REGION_EXACT,
        airports=[]
    )

    candidates = [item1, item2, item3]
    result = deduplicate_and_sort(candidates)

    # Expect: 2 items, sorted MIA (1090) first, TPA (820) second
    assert len(result) == 2
    assert result[0].id == "airport:MIA"
    assert result[0].score == 1009
    assert result[1].id == "airport:TPA"
    assert result[1].score == 820
