import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.translation_service import TranslationService, should_try_translation, TranslationResult
from app.core.config import settings

def test_should_try_translation():
    # True cases
    assert should_try_translation("ภูเก็ต") is True
    assert should_try_translation("昌迪加尔") is True
    assert should_try_translation("दिल्ली") is True
    assert should_try_translation("Москва") is True
    
    # False cases
    assert should_try_translation("LHR") is False
    assert should_try_translation("Goa") is False
    assert should_try_translation("LON") is False
    assert should_try_translation("123456") is False
    assert should_try_translation("") is False
    assert should_try_translation("   ") is False
    assert should_try_translation("a") is False  # too short (length < 2)

def test_translation_disabled():
    # Save original settings
    original_enabled = settings.ENABLE_TRANSLATION_FALLBACK
    settings.ENABLE_TRANSLATION_FALLBACK = False
    
    try:
        service = TranslationService()
        res = asyncio.run(service.translate_to_english("ภูเก็ต"))
        assert res is None
    finally:
        settings.ENABLE_TRANSLATION_FALLBACK = original_enabled

def test_translation_api_key_missing():
    original_enabled = settings.ENABLE_TRANSLATION_FALLBACK
    original_key = settings.GOOGLE_TRANSLATE_API_KEY
    
    settings.ENABLE_TRANSLATION_FALLBACK = True
    settings.GOOGLE_TRANSLATE_API_KEY = ""
    
    try:
        service = TranslationService()
        res = asyncio.run(service.translate_to_english("ภูเก็ต"))
        assert res is None
    finally:
        settings.ENABLE_TRANSLATION_FALLBACK = original_enabled
        settings.GOOGLE_TRANSLATE_API_KEY = original_key

def test_translation_caching_and_mock_api():
    original_enabled = settings.ENABLE_TRANSLATION_FALLBACK
    original_key = settings.GOOGLE_TRANSLATE_API_KEY
    
    settings.ENABLE_TRANSLATION_FALLBACK = True
    settings.GOOGLE_TRANSLATE_API_KEY = "fake-api-key"
    
    mock_response_data = {
        "data": {
            "translations": [
                {
                    "translatedText": "Phuket",
                    "detectedSourceLanguage": "th"
                }
            ]
        }
    }
    
    service = TranslationService()
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response_data
        mock_post.return_value = mock_resp
        
        # First call (cache miss)
        res1 = asyncio.run(service.translate_to_english("ภูเก็ต"))
        assert res1 is not None
        assert res1.translated_text == "Phuket"
        assert res1.detected_language == "th"
        assert res1.cache_hit is False
        assert mock_post.call_count == 1
        
        # Second call (cache hit)
        res2 = asyncio.run(service.translate_to_english("ภูเก็ต"))
        assert res2 is not None
        assert res2.translated_text == "Phuket"
        assert res2.detected_language == "th"
        assert res2.cache_hit is True
        # Post count should still be 1 because it loaded from cache
        assert mock_post.call_count == 1
        
    settings.ENABLE_TRANSLATION_FALLBACK = original_enabled
    settings.GOOGLE_TRANSLATE_API_KEY = original_key
