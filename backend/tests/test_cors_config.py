import pytest
from app.core.config import Settings

def test_cors_origins_parsing_wildcard():
    settings = Settings(BACKEND_CORS_ORIGINS="*")
    assert settings.BACKEND_CORS_ORIGINS == ["*"]
    assert settings.CORS_ALLOW_CREDENTIALS is False

def test_cors_origins_parsing_comma_separated():
    settings = Settings(BACKEND_CORS_ORIGINS="https://flyfair.devinderpanesar.com, http://localhost:5173")
    assert settings.BACKEND_CORS_ORIGINS == ["https://flyfair.devinderpanesar.com", "http://localhost:5173"]
    assert settings.CORS_ALLOW_CREDENTIALS is True

def test_cors_origins_parsing_spaces():
    settings = Settings(BACKEND_CORS_ORIGINS="   https://a.com   ,   https://b.com   ")
    assert settings.BACKEND_CORS_ORIGINS == ["https://a.com", "https://b.com"]
    assert settings.CORS_ALLOW_CREDENTIALS is True
