import re
from unidecode import unidecode
from app.models.search_models import NormalizedQuery

def normalize_query(query: str) -> NormalizedQuery:
    """Normalize input search query to support multiple matching paths (accents, cases, scripts)."""
    if query is None:
        query = ""
    # Trim whitespace
    raw = query.strip()
    
    # Lowercase
    lower = raw.lower()
    
    # Collapse multiple spaces
    collapsed = re.sub(r'\s+', ' ', lower)
    
    raw_normalized = collapsed
    latin_folded_normalized = unidecode(collapsed).strip().lower()
    
    # If it contains non-Latin scripts (outside ASCII + Latin Extensions + General Punctuation)
    # we preserve the original script. Otherwise we use the accent-folded version.
    if re.search(r'[^\u0000-\u024F\u1E00-\u1EFF\u2000-\u206F]', collapsed):
        normalized = raw_normalized
    else:
        normalized = latin_folded_normalized
    
    # Uppercase representation for code matching (IATA/ICAO)
    upper = collapsed.upper()
    
    return NormalizedQuery(
        raw=raw,
        lower=lower,
        normalized=normalized,
        upper=upper,
        rawNormalized=raw_normalized,
        latinFoldedNormalized=latin_folded_normalized
    )

def is_subsequence(query: str, text: str) -> bool:
    """Returns True if all chars in query appear in text in order."""
    if not query or not text:
        return False
        
    query_norm = normalize_query(query).normalized
    text_norm = normalize_query(text).normalized
    
    # Don't use subsequence for single char
    if len(query_norm) < 2:
        return False
        
    # Product optimization: subsequence must start with the same character
    if text_norm[0] != query_norm[0]:
        return False
        
    it = iter(text_norm)
    return all(char in it for char in query_norm)

def normalized_contains(query: str, text: str) -> bool:
    """Returns True if normalized query is a substring of normalized text."""
    if not query or not text:
        return False
        
    query_norm = normalize_query(query).normalized
    text_norm = normalize_query(text).normalized
    
    return query_norm in text_norm
