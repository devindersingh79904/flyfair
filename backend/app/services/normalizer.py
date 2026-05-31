import re
from unidecode import unidecode
from app.models.search_models import NormalizedQuery

def normalize_query(query: str) -> NormalizedQuery:
    """Normalize input search query to support multiple matching paths (accents, cases, scripts)."""
    # Trim whitespace
    raw = query.strip()
    
    # Lowercase
    lower = raw.lower()
    
    # Collapse multiple spaces
    collapsed = re.sub(r'\s+', ' ', lower)
    
    # Accent folding for Latin characters (e.g., München -> munchen, São Paulo -> sao paulo)
    normalized = unidecode(collapsed).strip().lower()
    
    # Uppercase representation for code matching (IATA/ICAO)
    upper = collapsed.upper()
    
    return NormalizedQuery(
        raw=raw,
        lower=lower,
        normalized=normalized,
        upper=upper
    )
