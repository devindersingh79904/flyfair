import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union
from pydantic import field_validator

# Resolve base directory containing .env file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILE_PATH = os.path.join(BASE_DIR, ".env")

class Settings(BaseSettings):
    APP_NAME: str = "Fly Fairly Airport Search API"
    APP_ENV: str = "local"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    LOG_LEVEL: str = "INFO"

    # Search behavior
    ENABLE_FUZZY_SEARCH: bool = True
    ENABLE_SUBSTRING_MATCH: bool = True
    ENABLE_SUBSEQUENCE_MATCH: bool = True
    FUZZY_MIN_QUERY_LENGTH: int = 4
    FUZZY_THRESHOLD: float = 82.0
    PREFIX_MIN_QUERY_LENGTH: int = 1
    SUBSTRING_MIN_QUERY_LENGTH: int = 2
    SUBSEQUENCE_MIN_QUERY_LENGTH: int = 3
    MAX_SEARCH_RESULTS: int = 20
    DEFAULT_SEARCH_LIMIT: int = 10
    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def CORS_ALLOW_CREDENTIALS(self) -> bool:
        return "*" not in self.BACKEND_CORS_ORIGINS

settings = Settings()
