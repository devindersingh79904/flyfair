import pytest
from app.services.index_builder import IndexBuilder
from app.services.airport_search_service import AirportSearchService
from app.core.constants import MatchReason
import os

@pytest.fixture
def search_service():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "app", "data")
    idx = IndexBuilder(data_dir=data_dir)
    return AirportSearchService(index=idx)

def test_exact_multilingual(search_service):
    cases = [
        ("北京", "city_group:beijing-cn"),
        ("東京", "city_group:tokyo-jp"),
        ("伦敦", "city_group:london-gb"),
        ("دبي", "airport:DXB"),
        ("दिल्ली", "airport:DEL"),
        ("मुंबई", "airport:BOM"),
        ("बेंगलुरु", "airport:BLR"),
        ("서울", "city_group:seoul-kr"),
    ]
    for q, expected_id in cases:
        res, _ = search_service.search(q, limit=1)
        assert len(res.results) > 0, f"No results for {q}"
        assert res.results[0].id == expected_id, f"Expected {expected_id} for {q}, got {res.results[0].id}"
        assert res.results[0].matchReason == MatchReason.ALIAS_EXACT

def test_accent(search_service):
    res1, _ = search_service.search("São Paulo", limit=1)
    res2, _ = search_service.search("Sao Paulo", limit=1)
    assert res1.results[0].id == res2.results[0].id
    
    res3, _ = search_service.search("München", limit=1)
    res4, _ = search_service.search("Munchen", limit=1)
    assert res3.results[0].id == res4.results[0].id

def test_prefix_multilingual(search_service):
    res, _ = search_service.search("दिल", limit=1)
    assert len(res.results) > 0
    
    res, _ = search_service.search("伦", limit=1)
    assert len(res.results) > 0

    res, _ = search_service.search("د", limit=1)
    assert len(res.results) > 0

