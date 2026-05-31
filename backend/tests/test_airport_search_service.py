import os
import pytest
from app.services.index_builder import IndexBuilder
from app.services.airport_search_service import AirportSearchService
from app.core.constants import ResultType, MatchReason

@pytest.fixture(scope="module")
def search_service():
    """Fixture to instantiate the search service using the live test database."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "app", "data")
    index = IndexBuilder(data_dir=data_dir)
    return AirportSearchService(index=index)

def test_search_hawaii(search_service):
    # 1. q=Hawaii => REGION_GROUP Hawaii, includes HNL, OGG, KOA, LIH
    res, _ = search_service.search("Hawaii", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert top.type == ResultType.REGION_GROUP
    assert "Hawaii" in top.displayName
    iatas = [ap.iata for ap in top.airports]
    for code in ["HNL", "OGG", "KOA", "LIH"]:
        assert code in iatas
    
    # Assert child airports are NOT repeated as top-level results
    top_level_ids = [r.id for r in res.results]
    for code in ["HNL", "OGG", "KOA", "LIH"]:
        assert f"airport:{code}" not in top_level_ids

def test_search_bali(search_service):
    # 2. q=Bali => DPS first, Balikpapan (BPN) is not first
    res, _ = search_service.search("Bali", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert "DPS" in [ap.iata for ap in top.airports]
    # Check that BPN is either lower or not top
    if len(res.results) > 1:
        bpn_indices = [i for i, r in enumerate(res.results) if "BPN" in [ap.iata for ap in r.airports]]
        for idx in bpn_indices:
            assert idx > 0

def test_search_florida(search_service):
    # 3. q=Florida => REGION_GROUP Florida first, La Florida Chile not first
    res, _ = search_service.search("Florida", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert top.type == ResultType.REGION_GROUP
    assert "Florida" in top.displayName
    assert "US" in top.countryCode
    
    # La Florida Chile has IATA LSC. Let's make sure it's not first
    if len(res.results) > 1:
        lsc_indices = [i for i, r in enumerate(res.results) if "LSC" in [ap.iata for ap in r.airports]]
        for idx in lsc_indices:
            assert idx > 0

def test_search_manama(search_service):
    # 4. q=Manama => BAH appears
    res, _ = search_service.search("Manama", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert "BAH" in [ap.iata for ap in top.airports]

def test_search_bengaluru_and_bangalore(search_service):
    # 5. q=Bengaluru & 6. q=Bangalore => BLR appears
    res_beng, _ = search_service.search("Bengaluru", limit=10)
    assert len(res_beng.results) > 0
    assert "BLR" in [ap.iata for ap in res_beng.results[0].airports]

    res_bang, _ = search_service.search("Bangalore", limit=10)
    assert len(res_bang.results) > 0
    assert "BLR" in [ap.iata for ap in res_bang.results[0].airports]

def test_search_tulsa(search_service):
    # 7. q=TUL => TUL first (IATA_EXACT)
    res_tul, _ = search_service.search("TUL", limit=10)
    assert len(res_tul.results) > 0
    assert res_tul.results[0].matchReason == MatchReason.IATA_EXACT
    assert "TUL" in [ap.iata for ap in res_tul.results[0].airports]

    # 8. q=Tulsa => TUL appears
    res_tuls, _ = search_service.search("Tulsa", limit=10)
    assert len(res_tuls.results) > 0
    assert "TUL" in [ap.iata for ap in res_tuls.results[0].airports]

def test_search_catania(search_service):
    # 9. q=CTA => CTA first (IATA_EXACT)
    res_cta, _ = search_service.search("CTA", limit=10)
    assert len(res_cta.results) > 0
    assert res_cta.results[0].matchReason == MatchReason.IATA_EXACT
    assert "CTA" in [ap.iata for ap in res_cta.results[0].airports]

    # 10. q=Catania => CTA appears
    res_cat, _ = search_service.search("Catania", limit=10)
    assert len(res_cat.results) > 0
    assert "CTA" in [ap.iata for ap in res_cat.results[0].airports]

def test_search_brussels(search_service):
    # 11. q=Brussels & 12. q=Zaventem => BRU appears
    res_bru, _ = search_service.search("Brussels", limit=10)
    assert len(res_bru.results) > 0
    assert "BRU" in [ap.iata for ap in res_bru.results[0].airports]

    res_zav, _ = search_service.search("Zaventem", limit=10)
    assert len(res_zav.results) > 0
    assert "BRU" in [ap.iata for ap in res_zav.results[0].airports]

def test_search_london_typo(search_service):
    # 13. q=Londn => London UK appears top
    res, _ = search_service.search("Londn", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert "London" in top.displayName
    assert "GB" in top.countryCode or "United Kingdom" in top.country
    assert top.matchReason in (MatchReason.FUZZY_CITY, MatchReason.FUZZY_AIRPORT, MatchReason.SUBSEQUENCE_MATCH)

def test_search_london_code(search_service):
    # 14. q=LON => London UK first (CITY_CODE_EXACT)
    res, _ = search_service.search("LON", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert top.matchReason in (MatchReason.CITY_CODE_EXACT, MatchReason.ALIAS_EXACT)
    assert "LON" in top.id or "london-gb" in top.id
    iatas = [ap.iata for ap in top.airports]
    for code in ["LHR", "LGW", "STN", "LCY", "LTN"]:
        assert code in iatas

    # Assert child airports are NOT repeated as top-level results
    top_level_ids = [r.id for r in res.results]
    for code in ["LHR", "LGW", "STN", "LCY", "LTN"]:
        assert f"airport:{code}" not in top_level_ids

def test_search_london_disambiguation(search_service):
    # 15. q=London => London UK group first, Ontario second, Kentucky third
    res, _ = search_service.search("London", limit=20)
    assert len(res.results) >= 3
    
    # Extract order of London groups
    matches = [r.id for r in res.results if "london" in r.id]
    assert "city_group:london-gb" in matches
    assert "city_group:london-ca" in matches
    assert "city_group:london-us-ky" in matches

    # Confirm correct ranking sequence
    gb_idx = matches.index("city_group:london-gb")
    ca_idx = matches.index("city_group:london-ca")
    ky_idx = matches.index("city_group:london-us-ky")
    assert gb_idx < ca_idx < ky_idx

def test_search_multilingual(search_service):
    # 16. q=東京 => Tokyo group
    res_tok, _ = search_service.search("東京", limit=10)
    assert len(res_tok.results) > 0
    assert "city_group:tokyo-jp" in [r.id for r in res_tok.results]

    # 17. q=北京 => Beijing group
    res_bej, _ = search_service.search("北京", limit=10)
    assert len(res_bej.results) > 0
    assert "city_group:beijing-cn" in [r.id for r in res_bej.results]

    # 18. q=서울 => Seoul group
    res_seo, _ = search_service.search("서울", limit=10)
    assert len(res_seo.results) > 0
    assert "city_group:seoul-kr" in [r.id for r in res_seo.results]

    # 19. q=دبي => DXB
    res_dub, _ = search_service.search("دبي", limit=10)
    assert len(res_dub.results) > 0
    assert "airport:DXB" in [r.id for r in res_dub.results] or "city_group:dubai" in [r.id for r in res_dub.results]

def test_search_accent_folding(search_service):
    # 20. q=Sao Paulo => São Paulo group
    res1, _ = search_service.search("Sao Paulo", limit=10)
    assert len(res1.results) > 0
    assert "city_group:sao-paulo-br" in [r.id for r in res1.results]

    # 21. q=São Paulo => Same top result
    res2, _ = search_service.search("São Paulo", limit=10)
    assert len(res2.results) > 0
    assert res1.results[0].id == res2.results[0].id

def test_search_munich(search_service):
    # 22. q=München & 23. q=Munchen => MUC
    res1, _ = search_service.search("München", limit=10)
    assert len(res1.results) > 0
    assert "airport:MUC" in [r.id for r in res1.results]

    res2, _ = search_service.search("Munchen", limit=10)
    assert len(res2.results) > 0
    assert "airport:MUC" in [r.id for r in res2.results]

def test_search_goa_and_ontario(search_service):
    # 24. q=Goa => Goa city group / airports
    res_goa, _ = search_service.search("Goa", limit=10)
    assert len(res_goa.results) > 0
    # Confirm Goa or GOI/GOX is present
    match_ids = [r.id for r in res_goa.results]
    assert any("goa" in mid or "GOI" in mid or "GOX" in mid for mid in match_ids)

    # 25. q=Ontario => Ontario region group
    res_ont, _ = search_service.search("Ontario", limit=10)
    assert len(res_ont.results) > 0
    assert "region:ca-on" in [r.id for r in res_ont.results]

def test_search_chandigarh(search_service):
    # q=Chandigarh -> IXC
    res, _ = search_service.search("Chandigarh", limit=10)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:IXC"

    # q=IXC -> IXC
    res, _ = search_service.search("IXC", limit=10)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:IXC"

    # q=Mohali -> IXC
    res, _ = search_service.search("Mohali", limit=10)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:IXC"

def test_hierarchical_city_groups(search_service):
    # LON top result is city group and contains child airports
    res, _ = search_service.search("LON", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert top.type == ResultType.CITY_GROUP
    assert len(top.airports) > 0

    # 北京
    res, _ = search_service.search("北京", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert top.id == "city_group:beijing-cn"

    # 서울
    res, _ = search_service.search("서울", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert top.id == "city_group:seoul-kr"

    # 東京
    res, _ = search_service.search("東京", limit=10)
    assert len(res.results) > 0
    top = res.results[0]
    assert top.id == "city_group:tokyo-jp"


def test_short_query_prefix(search_service):
    # q="i" returns non-empty results
    res, _ = search_service.search("i", limit=10)
    assert len(res.results) > 0
    # q="ix" returns at least one airport whose IATA starts with IX
    res_ix, _ = search_service.search("ix", limit=10)
    assert len(res_ix.results) > 0
    iata_codes = [ap.iata for r in res_ix.results for ap in r.airports]
    assert any(code.startswith("IX") for code in iata_codes if code)
    
    # q="lhr" returns airport:LHR first
    res_lhr, _ = search_service.search("lhr", limit=10)
    assert len(res_lhr.results) > 0
    assert res_lhr.results[0].id == "airport:LHR"
    
    # q="lon" returns city_group:london-gb first
    res_lon, _ = search_service.search("lon", limit=10)
    assert len(res_lon.results) > 0
    assert res_lon.results[0].id == "city_group:london-gb"
    
    # q="dub" includes DXB or Dubai
    res_dub, _ = search_service.search("dub", limit=10)
    assert len(res_dub.results) > 0
    assert any(r.id == "airport:DXB" or "dubai" in r.id for r in res_dub.results)
    
    # q="chd" returns CHD if present, >1 result
    res_chd, _ = search_service.search("chd", limit=10)
    assert len(res_chd.results) >= 1

def test_no_fuzzy_for_short_queries(search_service):
    res_i, _ = search_service.search("i", limit=10)
    for r in res_i.results:
        assert "FUZZY" not in str(r.matchReason)
        
    res_ix, _ = search_service.search("ix", limit=10)
    for r in res_ix.results:
        assert "FUZZY" not in str(r.matchReason)

def test_direct_airport_search_hnl(search_service):
    # Direct search for HNL should return HNL as top-level AIRPORT
    res, _ = search_service.search("HNL", limit=10)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:HNL"

def test_direct_airport_search_lhr(search_service):
    # Direct search for LHR should return LHR as top-level AIRPORT
    res, _ = search_service.search("LHR", limit=10)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:LHR"
