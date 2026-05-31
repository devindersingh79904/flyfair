import pytest
from app.services.index_builder import IndexBuilder
from app.services.airport_search_service import AirportSearchService
from app.core.constants import MatchReason
from scripts.generate_multilingual_aliases import detect_script
import os

@pytest.fixture
def search_service():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "app", "data")
    idx = IndexBuilder(data_dir=data_dir)
    return AirportSearchService(index=idx)

def test_detect_script():
    assert detect_script("北京") in ["Han", "Japanese"] # CJK characters
    assert detect_script("東京") in ["Han", "Japanese"]
    assert detect_script("서울") == "Hangul"
    assert detect_script("دبي") == "Arabic"
    assert detect_script("Москва") == "Cyrillic"
    assert detect_script("กรุงเทพ") == "Thai"
    assert detect_script("दिल्ली") == "Devanagari"
    assert detect_script("London") == "Latin"

def test_search_cjk(search_service):
    res, _ = search_service.search("北京", limit=1)
    assert len(res.results) > 0
    assert res.results[0].id == "city_group:beijing-cn"
    
    res, _ = search_service.search("東京", limit=1)
    assert len(res.results) > 0
    assert res.results[0].id == "city_group:tokyo-jp"

def test_search_arabic(search_service):
    res, _ = search_service.search("دبي", limit=1)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:DXB"

def test_search_korean(search_service):
    res, _ = search_service.search("서울", limit=1)
    assert len(res.results) > 0
    assert res.results[0].id == "city_group:seoul-kr"

def test_search_hindi(search_service):
    res, _ = search_service.search("दिल्ली", limit=1)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:DEL"
    
    res, _ = search_service.search("मुंबई", limit=1)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:BOM"

def test_search_cyrillic(search_service):
    # Москва might map to SVO or city_group if present
    res, _ = search_service.search("Москва", limit=1)
    assert len(res.results) > 0

def test_search_thai(search_service):
    # กรุงเทพ should map to BKK or city group
    res, _ = search_service.search("กรุงเทพ", limit=1)
    assert len(res.results) > 0

def test_search_latin_diacritics(search_service):
    res1, _ = search_service.search("São Paulo", limit=1)
    res2, _ = search_service.search("Sao Paulo", limit=1)
    assert res1.results[0].id == res2.results[0].id
    assert res1.results[0].id == "city_group:sao-paulo-br"
