from typing import Literal

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
    # "background": POST returns at once and the client polls (needs one long-running
    # server, since jobs live in memory). "inline": POST waits and returns the finished
    # search, for serverless hosts where the next request may reach another instance.
    search_mode: Literal["background", "inline"] = "background"
    # Flipkart rate-limits its product pages for shared cloud addresses (Vercel), but not
    # for a server with its own address. When set, Flipkart product pages are read by the
    # backend at this URL (the same app, deployed on Fly.io) instead of directly.
    flipkart_relay_url: str = ""
    # Shared secret between the two backends. The relay route is off when it is empty.
    relay_token: str = ""


settings = Settings()
