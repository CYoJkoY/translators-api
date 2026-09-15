from __future__ import annotations

from functools import lru_cache
import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    api_key: str | None = Field(default=None)
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    max_text_length: int = 20_000
    max_batch_items: int = 50
    max_batch_total_length: int = 100_000
    max_batch_concurrency: int = 5
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    fallback_translators: list[str] = Field(
        default_factory=lambda: ["bing", "google", "deepl", "baidu"]
    )
    default_translator: str = "bing"


def _csv(value: str | None, fallback: list[str]) -> list[str]:
    if not value:
        return fallback
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    defaults = Settings()
    return Settings(
        api_key=os.getenv("TRANSLATORS_API_KEY") or None,
        host=os.getenv("HOST", defaults.host),
        port=int(os.getenv("PORT", str(defaults.port))),
        log_level=os.getenv("LOG_LEVEL", defaults.log_level),
        max_text_length=int(os.getenv("MAX_TEXT_LENGTH", str(defaults.max_text_length))),
        max_batch_items=int(os.getenv("MAX_BATCH_ITEMS", str(defaults.max_batch_items))),
        max_batch_total_length=int(
            os.getenv("MAX_BATCH_TOTAL_LENGTH", str(defaults.max_batch_total_length))
        ),
        max_batch_concurrency=int(
            os.getenv("MAX_BATCH_CONCURRENCY", str(defaults.max_batch_concurrency))
        ),
        rate_limit_requests=int(
            os.getenv("RATE_LIMIT_REQUESTS", str(defaults.rate_limit_requests))
        ),
        rate_limit_window_seconds=int(
            os.getenv("RATE_LIMIT_WINDOW_SECONDS", str(defaults.rate_limit_window_seconds))
        ),
        fallback_translators=_csv(
            os.getenv("FALLBACK_TRANSLATORS"), defaults.fallback_translators
        ),
        default_translator=os.getenv("DEFAULT_TRANSLATOR", defaults.default_translator),
    )
