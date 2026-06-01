import html
import re
import logging
from collections import OrderedDict
from typing import Optional
import httpx

from app.core.config import settings
from app.core.constants import TRANSLATION_PROVIDER_GOOGLE
from app.services.normalizer import normalize_query

logger = logging.getLogger(__name__)

# Regex for non-Latin script characters:
# Thai: \u0e00-\u0e7f
# CJK Unified Ideographs (Chinese Han): \u4e00-\u9fff, CJK Unified Ideographs Extension A: \u3400-\u4dbf
# Japanese Hiragana: \u3040-\u309f, Katakana: \u30a0-\u30ff
# Hangul: Syllables \uac00-\ud7af, Jamo \u1100-\u11ff, Compatibility Jamo \u3130-\u318f
# Arabic: \u0600-\u06ff, \u0750-\u077f, \u08a0-\u08ff
# Cyrillic: \u0400-\u04ff, \u0500-\u052f
# Devanagari: \u0900-\u097f
NON_LATIN_SCRIPTS_RE = re.compile(
    r'['
    r'\u0e00-\u0e7f'                          # Thai
    r'\u4e00-\u9fff\u3400-\u4dbf'              # Han/CJK
    r'\u3040-\u30ff'                          # Japanese Hiragana/Katakana
    r'\uac00-\ud7af\u1100-\u11ff\u3130-\u318f'  # Hangul
    r'\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff'  # Arabic
    r'\u0400-\u04ff\u0500-\u052f'              # Cyrillic
    r'\u0900-\u097f'                          # Devanagari
    r']'
)

def should_try_translation(query: str) -> bool:
    """
    Returns True if the query looks like a non-English/non-Latin query that needs translation.
    - query contains non-Latin script characters (Thai, Han/CJK, Hiragana/Katakana, Hangul, Arabic, Cyrillic, Devanagari)
    - query length >= TRANSLATION_MIN_QUERY_LENGTH
    
    Returns False for:
    - pure ASCII / English
    - IATA codes like LHR, GOA, IXC
    - numbers/symbols only
    - empty query
    """
    if not query:
        return False
        
    trimmed = query.strip()
    if len(trimmed) < settings.TRANSLATION_MIN_QUERY_LENGTH:
        return False
        
    # Check if query contains any of the specified non-Latin script characters
    if not NON_LATIN_SCRIPTS_RE.search(trimmed):
        return False
        
    return True

class TranslationResult:
    def __init__(
        self,
        original_text: str,
        translated_text: str,
        detected_language: Optional[str],
        provider: str,
        cache_hit: bool = False
    ):
        self.original_text = original_text
        self.translated_text = translated_text
        self.detected_language = detected_language
        self.provider = provider
        self.cache_hit = cache_hit

    def to_dict(self):
        return {
            "original_text": self.original_text,
            "translated_text": self.translated_text,
            "detected_language": self.detected_language,
            "provider": self.provider,
            "cache_hit": self.cache_hit
        }

class TranslationService:
    def __init__(self):
        self.max_cache_size = settings.TRANSLATION_CACHE_MAX_SIZE
        self.cache: OrderedDict[str, TranslationResult] = OrderedDict()

    def _get_cache(self, key: str) -> Optional[TranslationResult]:
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def _put_cache(self, key: str, value: TranslationResult):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.max_cache_size:
            self.cache.popitem(last=False)

    async def translate_to_english(self, text: str) -> Optional[TranslationResult]:
        if not text:
            return None
            
        trimmed = text.strip()
        if not trimmed:
            return None
            
        if len(trimmed) > settings.TRANSLATION_MAX_QUERY_LENGTH:
            logger.info(f"Query too long for translation: length={len(trimmed)}")
            return None
            
        if not should_try_translation(trimmed):
            return None
            
        if not settings.IS_TRANSLATION_ENABLED:
            logger.info("Translation fallback is disabled in settings.")
            return None

        # Normalize key for cache lookup
        normalized_key = normalize_query(trimmed).normalized
        
        cached = self._get_cache(normalized_key)
        if cached:
            logger.info(
                f"Translation cache hit: query='{trimmed}' "
                f"normalized='{normalized_key}' -> '{cached.translated_text}'"
            )
            return TranslationResult(
                original_text=cached.original_text,
                translated_text=cached.translated_text,
                detected_language=cached.detected_language,
                provider=cached.provider,
                cache_hit=True
            )
            
        logger.info(f"Translation cache miss: query='{trimmed}' normalized='{normalized_key}'")

        url = "https://translation.googleapis.com/language/translate/v2"
        params = {"key": settings.GOOGLE_TRANSLATE_API_KEY}
        data = {
            "q": [trimmed],
            "target": settings.GOOGLE_TRANSLATE_TARGET_LANGUAGE
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    params=params,
                    json=data,
                    timeout=settings.TRANSLATION_REQUEST_TIMEOUT_SECONDS
                )
                
            response.raise_for_status()
            res_json = response.json()
            
            translations = res_json.get("data", {}).get("translations", [])
            if not translations:
                logger.warning("Empty translations returned from Google Translate API.")
                return None
                
            translation = translations[0]
            translated_text_raw = translation.get("translatedText")
            detected_lang = translation.get("detectedSourceLanguage")
            
            if not translated_text_raw:
                return None
                
            translated_text = html.unescape(translated_text_raw)
            
            result = TranslationResult(
                original_text=trimmed,
                translated_text=translated_text,
                detected_language=detected_lang,
                provider=TRANSLATION_PROVIDER_GOOGLE,
                cache_hit=False
            )
            
            self._put_cache(normalized_key, result)
            logger.info(
                f"Translation API call succeeded: original='{trimmed}' "
                f"translated='{translated_text}' lang='{detected_lang}'"
            )
            return result
            
        except Exception as e:
            # Never print the API key (which is in params) or expose it in logs
            logger.error(f"Google translation API request failed: {str(e)}")
            return None
