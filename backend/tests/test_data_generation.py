import pytest
from scripts.generate_airport_data import (
    generate_aliases,
    clean_alias,
    VALID_TYPES,
    INVALID_TYPES,
    MAJOR_HUBS
)

def test_clean_alias():
    assert clean_alias("  New   York  ") == "new york"
    assert clean_alias(None) == ""
    assert clean_alias("") == ""

def test_generate_aliases():
    aliases = generate_aliases(
        iata="JFK",
        city="New York",
        name="John F Kennedy International Airport",
        country="United States"
    )
    
    # Should include base fields
    assert "jfk" in aliases
    assert "new york" in aliases
    assert "john f kennedy international airport" in aliases
    
    # Should not include country
    assert "united states" not in aliases
    
def test_generate_aliases_with_accents():
    aliases = generate_aliases(
        iata="YUL",
        city="Montréal",
        name="Montréal-Pierre Elliott Trudeau International Airport",
        country="Canada"
    )
    
    # Should include both accented and unaccented versions
    assert "montréal" in aliases
    assert "montreal" in aliases
    
def test_generate_aliases_excludes_country():
    aliases = generate_aliases(
        iata="SIN",
        city="Singapore",
        name="Singapore Changi Airport",
        country="Singapore"
    )
    
    # "singapore" should be excluded since it matches country name exactly
    assert "singapore" not in aliases
    assert "sin" in aliases
    assert "singapore changi airport" in aliases

def test_valid_types():
    assert "large_airport" in VALID_TYPES
    assert "medium_airport" in VALID_TYPES
    assert "small_airport" in VALID_TYPES
    
    assert "heliport" in INVALID_TYPES
    assert "closed" in INVALID_TYPES
