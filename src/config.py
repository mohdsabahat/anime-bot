"""
Shared application settings for both the bot and API.

Centralizes common configuration to avoid duplicate pydantic-settings
parsing and "extra inputs" warnings when different modules load
their own BaseSettings instances.
"""
from pydantic_settings import BaseSettings


class CommonSettings(BaseSettings):
    # Database configuration
    database_url: str = "sqlite+aiosqlite:///./data/anime_files.db"

    # Logging
    log_level: str = "INFO"

    env: str = "development"
    debug: bool = True

    # Pydantic v2 configuration: accept extra env vars and set env file
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


__all__ = ["CommonSettings"]
