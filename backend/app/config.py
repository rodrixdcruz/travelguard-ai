"""Application configuration via environment variables (12-factor)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TravelGuard AI"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str | None = None

    weather_api_key: str | None = None
    routing_api_url: str | None = None
    accident_api_key: str | None = None

    ai_api_key: str | None = None
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"

    frontend_url: str = "http://localhost:5173"


settings = Settings()
