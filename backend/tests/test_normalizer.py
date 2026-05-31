from app.services.normalizer import normalize_query

def test_normalizer_accents():
    res = normalize_query(" São   Paulo ")
    assert res.normalized == "sao paulo"
    assert res.raw == "São   Paulo"
    assert res.lower == "são   paulo"

    res = normalize_query("München")
    assert res.normalized == "munchen"

def test_normalizer_spaces():
    res = normalize_query("   multiple    spaces    ")
    assert res.normalized == "multiple spaces"
    assert res.lower == "multiple    spaces"

def test_normalizer_non_latin():
    res = normalize_query("東京")
    # unidecode turns "東京" into "Dong Jing" (transliterated)
    # but lower and raw must preserve native glyphs
    assert res.lower == "東京"
    assert res.raw == "東京"
    
    res = normalize_query("서울")
    assert res.lower == "서울"
    assert res.raw == "서울"
