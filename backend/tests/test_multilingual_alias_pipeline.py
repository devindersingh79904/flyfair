import pytest
from app.services.index_builder import IndexBuilder
from app.services.airport_search_service import AirportSearchService
from app.core.constants import MatchReason
from scripts.generate_multilingual_aliases import (
    detect_script, parse_row, parse_and_group, extract_iata_codes,
    generate_aliases_from_group, is_useful_alias, compute_priority,
    GeoNameAliasRow,
)
from app.services.normalizer import normalize_query
import os
import tempfile
import json

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def search_service():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "app", "data")
    idx = IndexBuilder(data_dir=data_dir)
    return AirportSearchService(index=idx)


@pytest.fixture
def airports_by_id():
    """Load real airports for use in pipeline unit tests."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "app", "data")
    with open(os.path.join(data_dir, "airports.json"), "r", encoding="utf-8") as f:
        airports = json.load(f)
    return {ap["id"]: ap for ap in airports}


# ---------------------------------------------------------------------------
# Script Detection Tests
# ---------------------------------------------------------------------------

def test_detect_script():
    assert detect_script("北京") in ["Han", "Japanese"]  # CJK characters
    assert detect_script("東京") in ["Han", "Japanese"]
    assert detect_script("서울") == "Hangul"
    assert detect_script("دبي") == "Arabic"
    assert detect_script("Москва") == "Cyrillic"
    assert detect_script("กรุงเทพ") == "Thai"
    assert detect_script("ภูเก็ต") == "Thai"
    assert detect_script("दिल्ली") == "Devanagari"
    assert detect_script("London") == "Latin"


def test_detect_script_thai_phuket():
    """ภูเก็ต must detect as Thai, not Other."""
    assert detect_script("ภูเก็ต") == "Thai"


def test_detect_script_thai_airport():
    """ท่าอากาศยานภูเก็ต must detect as Thai."""
    assert detect_script("ท่าอากาศยานภูเก็ต") == "Thai"


# ---------------------------------------------------------------------------
# Row Parser Tests
# ---------------------------------------------------------------------------

def test_parse_row_basic():
    line = "2729694\t1151254\tth\tภูเก็ต\t\t\t\t\t\t"
    row = parse_row(line)
    assert row is not None
    assert row.geoname_id == "1151254"
    assert row.language == "th"
    assert row.name == "ภูเก็ต"
    assert row.is_preferred is False


def test_parse_row_preferred():
    line = "13265393\t1151254\tko\t푸켓\t1\t\t\t\t\t"
    row = parse_row(line)
    assert row is not None
    assert row.is_preferred is True


def test_parse_row_iata():
    line = "7486583\t1151254\tiata\tHKT\t\t\t\t\t\t"
    row = parse_row(line)
    assert row is not None
    assert row.language == "iata"
    assert row.name == "HKT"


def test_parse_row_malformed():
    """Rows with fewer than 4 columns should return None."""
    assert parse_row("123\t456") is None
    assert parse_row("") is None
    assert parse_row("123\t456\t\t") is None  # empty name


def test_parse_row_missing_optional_cols():
    """Rows with only 4 columns (no optional flags) should parse fine."""
    line = "123\t456\ten\tPhuket"
    row = parse_row(line)
    assert row is not None
    assert row.name == "Phuket"
    assert row.is_preferred is False
    assert row.is_short is False


# ---------------------------------------------------------------------------
# Grouping & IATA Extraction Tests
# ---------------------------------------------------------------------------

def test_parse_and_group_sample():
    """Test grouping with a small sample file."""
    sample_lines = [
        "600856\t1151254\t\tPhuket\t\t\t\t\t\t\n",
        "2729694\t1151254\tth\tภูเก็ต\t\t\t\t\t\t\n",
        "7486583\t1151254\tiata\tHKT\t\t\t\t\t\t\n",
        "2930305\t1151254\tlink\thttps://en.wikipedia.org/wiki/Phuket\t\t\t\t\t\t\n",
        "1890233\t1115776\tiata\tMAQ\t\t\t\t\t\t\n",
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False,
                                     encoding="utf-8") as f:
        f.writelines(sample_lines)
        tmppath = f.name

    try:
        groups = parse_and_group(tmppath)
        assert "1151254" in groups
        assert len(groups["1151254"]) == 4
        assert "1115776" in groups
        assert len(groups["1115776"]) == 1
    finally:
        os.unlink(tmppath)


def test_extract_iata_codes():
    """IATA codes are extracted from rows with language='iata'."""
    rows = [
        GeoNameAliasRow("1", "100", "th", "ภูเก็ต"),
        GeoNameAliasRow("2", "100", "iata", "HKT"),
        GeoNameAliasRow("3", "100", "en", "Phuket"),
        GeoNameAliasRow("4", "100", "icao", "VTSP"),
    ]
    codes = extract_iata_codes(rows)
    assert codes == ["HKT"]


def test_extract_iata_codes_none():
    """No IATA rows means empty list."""
    rows = [
        GeoNameAliasRow("1", "200", "th", "กรุงเทพ"),
        GeoNameAliasRow("2", "200", "en", "Bangkok"),
    ]
    codes = extract_iata_codes(rows)
    assert codes == []


# ---------------------------------------------------------------------------
# Alias Filtering Tests
# ---------------------------------------------------------------------------

def test_is_useful_alias_metadata_skipped():
    """Metadata languages should be skipped."""
    for lang in ["link", "wkdt", "post", "unlc", "icao", "faac", "iata", "fr_1793", "abbr"]:
        row = GeoNameAliasRow("1", "100", lang, "SomeValue")
        assert is_useful_alias(row) is False, f"Language '{lang}' should be skipped"


def test_is_useful_alias_url_skipped():
    """URLs should be skipped."""
    row = GeoNameAliasRow("1", "100", "en", "https://en.wikipedia.org/wiki/Phuket")
    assert is_useful_alias(row) is False


def test_is_useful_alias_good():
    """Normal aliases should be kept."""
    row = GeoNameAliasRow("1", "100", "th", "ภูเก็ต")
    assert is_useful_alias(row) is True


def test_iata_language_used_for_linking_not_emitted():
    """IATA language rows should be used for linking but NOT emitted as aliases."""
    row = GeoNameAliasRow("1", "100", "iata", "HKT")
    assert is_useful_alias(row) is False


# ---------------------------------------------------------------------------
# IATA-Group Alias Generation Tests
# ---------------------------------------------------------------------------

def test_generate_aliases_hkt(airports_by_id):
    """Sample HKT geonameId group should produce Thai alias for airport:HKT."""
    group = [
        GeoNameAliasRow("600856", "1151254", "", "Phuket"),
        GeoNameAliasRow("2729694", "1151254", "th", "ภูเก็ต"),
        GeoNameAliasRow("7486583", "1151254", "iata", "HKT"),
        GeoNameAliasRow("2930305", "1151254", "link",
                        "https://en.wikipedia.org/wiki/Phuket"),
    ]

    iata_codes = extract_iata_codes(group)
    assert iata_codes == ["HKT"]

    aliases = generate_aliases_from_group(group, iata_codes, airports_by_id, "TH.txt")

    # Should have Phuket (English) and ภูเก็ต (Thai), NOT link or iata
    alias_names = [a["alias"] for a in aliases]
    assert "ภูเก็ต" in alias_names
    assert "Phuket" in alias_names
    assert "HKT" not in alias_names  # iata row is not emitted
    assert "https://en.wikipedia.org/wiki/Phuket" not in alias_names  # link skipped

    # Check target
    for a in aliases:
        assert a["targetId"] == "airport:HKT"
        assert a["targetType"] == "AIRPORT"


def test_generate_aliases_airport_entry(airports_by_id):
    """GeonameId 6301157 (Phuket airport) with IATA HKT and Thai airport name."""
    group = [
        GeoNameAliasRow("1890240", "6301157", "iata", "HKT"),
        GeoNameAliasRow("1887870", "6301157", "icao", "VTSP"),
        GeoNameAliasRow("5894052", "6301157", "th", "ท่าอากาศยานภูเก็ต"),
        GeoNameAliasRow("2729533", "6301157", "de", "Flughafen Phuket"),
        GeoNameAliasRow("5761211", "6301157", "link",
                        "https://en.wikipedia.org/wiki/Phuket_International_Airport"),
    ]

    iata_codes = extract_iata_codes(group)
    aliases = generate_aliases_from_group(group, iata_codes, airports_by_id, "TH.txt")

    alias_names = [a["alias"] for a in aliases]
    assert "ท่าอากาศยานภูเก็ต" in alias_names
    assert "Flughafen Phuket" in alias_names
    assert "VTSP" not in alias_names  # icao skipped
    assert "HKT" not in alias_names   # iata not emitted


# ---------------------------------------------------------------------------
# Priority Tests
# ---------------------------------------------------------------------------

def test_compute_priority_preferred():
    row = GeoNameAliasRow("1", "100", "th", "ภูเก็ต", is_preferred=True)
    assert compute_priority(row) == 92


def test_compute_priority_non_latin():
    row = GeoNameAliasRow("1", "100", "th", "ภูเก็ต")
    assert compute_priority(row) == 90


def test_compute_priority_english():
    row = GeoNameAliasRow("1", "100", "en", "Phuket")
    assert compute_priority(row) == 80


def test_compute_priority_historic():
    row = GeoNameAliasRow("1", "100", "en", "OldName", is_historic=True)
    assert compute_priority(row) == 60


def test_compute_priority_short():
    row = GeoNameAliasRow("1", "100", "en", "PHK", is_short=True)
    assert compute_priority(row) == 78


# ---------------------------------------------------------------------------
# Normalizer Tests
# ---------------------------------------------------------------------------

def test_normalize_thai():
    """Thai text should be preserved, not transliterated."""
    assert normalize_query("ภูเก็ต").normalized == "ภูเก็ต"


def test_normalize_cjk():
    """CJK text should be preserved."""
    assert normalize_query("東京").normalized == "東京"


def test_normalize_arabic():
    """Arabic text should be preserved."""
    assert normalize_query("دبي").normalized == "دبي"


def test_normalize_latin_accent():
    """Latin accented text should be folded."""
    assert normalize_query("São Paulo").normalized == "sao paulo"


# ---------------------------------------------------------------------------
# Integration Search Tests
# ---------------------------------------------------------------------------

def test_search_phuket_thai(search_service):
    """After loading generated multilingual_aliases.json, ภูเก็ต should find HKT."""
    res, _ = search_service.search("ภูเก็ต", limit=5)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:HKT"


def test_search_phuket_airport_thai(search_service):
    """ท่าอากาศยานภูเก็ต should find HKT."""
    res, _ = search_service.search("ท่าอากาศยานภูเก็ต", limit=5)
    assert len(res.results) > 0
    assert res.results[0].id == "airport:HKT"


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
