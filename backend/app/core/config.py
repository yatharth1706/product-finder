from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables (and `.env` if present)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Product Finder"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"

    # Comma-separated list of origins allowed to call the API (the frontend).
    cors_origins: str = "http://localhost:3000"

    # Outbound HTTP behaviour for extractors / marketplace adapters.
    http_timeout_seconds: float = 15.0
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
