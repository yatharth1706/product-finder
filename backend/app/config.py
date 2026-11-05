from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    cors_origins: list[str] = ["http://localhost:3000"]
    request_timeout_seconds: float = 15.0
    # Whole search on one marketplace, including availability checks.
    marketplace_timeout_seconds: float = 30.0
    # Product pages opened per marketplace to fill in colour or stock.
    max_detail_pages: int = 6
    log_level: str = "INFO"


settings = Settings()
