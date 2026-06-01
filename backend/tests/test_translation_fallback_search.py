import os
import pytest
from unittest.mock import AsyncMock, patch
from app.services.index_builder import IndexBuilder
from app.services.airport_search_service import AirportSearchService
from app.services.translation_service import TranslationService, TranslationResult
from app.core.config import settings

@pytest.fixture(scope="module")
def search_service():
    """Fixture to instantiate the search service using the live test database."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "app", "data")
    index = IndexBuilder(data_dir=data_dir)
    return AirportSearchService(index=index)

def test_no_fallback_when_strong_local(search_service):
    # Tokyo has a strong local alias match (東京 -> Tokyo city group, score 980)
    # Ensure translation fallback is NOT triggered.
    original_enabled = settings.ENABLE_TRANSLATION_FALLBACK
    settings.ENABLE_TRANSLATION_FALLBACK = True
    
    mock_service = AsyncMock(spec=TranslationService)
    search_service.translation_service = mock_service
    
    try:
        res, _ = search_service.search("東京", limit=10)
        assert len(res.results) > 0
        assert res.results[0].id == "city_group:tokyo-jp"
        assert res.translationFallbackUsed is False
        # translation service should not have been called because "東京" returned a strong local score
        assert mock_service.translate_to_english.call_count == 0
    finally:
        settings.ENABLE_TRANSLATION_FALLBACK = original_enabled
        search_service.translation_service = TranslationService()

def test_fallback_triggered_on_weak_local(search_service):
    # Use a query that has no local alias match: "สุวรรณภูมิ" (Suvarnabhumi Airport BKK)
    # We mock the translation to return "Suvarnabhumi".
    original_enabled = settings.ENABLE_TRANSLATION_FALLBACK
    original_key = settings.GOOGLE_TRANSLATE_API_KEY
    
    settings.ENABLE_TRANSLATION_FALLBACK = True
    settings.GOOGLE_TRANSLATE_API_KEY = "mock-key"
    
    mock_service = AsyncMock(spec=TranslationService)
    mock_service.translate_to_english.return_value = TranslationResult(
        original_text="สุวรรณภูมิ",
        translated_text="Suvarnabhumi",
        detected_language="th",
        provider="google",
        cache_hit=False
    )
    
    search_service.translation_service = mock_service
    
    try:
        res, _ = search_service.search("สุวรรณภูมิ", limit=10)
        
        # Should call translation service
        assert mock_service.translate_to_english.call_count == 1
        
        # Should return BKK because Suvarnabhumi maps to BKK
        assert len(res.results) > 0
        assert res.results[0].id == "airport:BKK"
        assert res.translationFallbackUsed is True
        assert res.translatedQuery == "Suvarnabhumi"
        assert res.detectedLanguage == "th"
        assert res.translationProvider == "google"
    finally:
        settings.ENABLE_TRANSLATION_FALLBACK = original_enabled
        settings.GOOGLE_TRANSLATE_API_KEY = original_key
        search_service.translation_service = TranslationService()

def test_provider_failure_graceful(search_service):
    # Mock translation to raise/fail. Search should complete gracefully returning empty/local results.
    original_enabled = settings.ENABLE_TRANSLATION_FALLBACK
    original_key = settings.GOOGLE_TRANSLATE_API_KEY
    
    settings.ENABLE_TRANSLATION_FALLBACK = True
    settings.GOOGLE_TRANSLATE_API_KEY = "mock-key"
    
    mock_service = AsyncMock(spec=TranslationService)
    mock_service.translate_to_english.side_effect = Exception("Google Translate API Down")
    
    search_service.translation_service = mock_service
    
    try:
        # This query should not crash
        res, _ = search_service.search("สุวรรณภูมิ", limit=10)
        assert res.translationFallbackUsed is False
        assert len(res.results) == 0  # no results, but no crash either!
    finally:
        settings.ENABLE_TRANSLATION_FALLBACK = original_enabled
        settings.GOOGLE_TRANSLATE_API_KEY = original_key
        search_service.translation_service = TranslationService()
