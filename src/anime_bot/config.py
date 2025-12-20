"""
Configuration module for anime-bot.

Uses pydantic-settings for environment variable loading and validation.
All settings can be configured via environment variables or a .env file.
"""
from pydantic_settings import BaseSettings
from src.config import CommonSettings


class Settings(CommonSettings):
    """Application settings loaded from environment variables."""

    # Telegram API credentials
    tg_api_id: int
    tg_api_hash: str
    tg_bot_token: str

    # Database configuration
    database_url: str = "sqlite+aiosqlite:///./data/anime_files.db"

    # File storage paths
    download_dir: str = "./data/downloads"
    archive_dir: str = "./data/archive"

    # Concurrency settings
    max_upload_concurrency: int = 2
    download_workers: int = 2

    # File management
    file_retention_seconds: int = 7 * 24 * 3600
    delete_after_upload: bool = True

    # Rate limiting
    rate_limit_seconds: float = 1.0

    # Logging
    log_level: str = "INFO"

    # Telegram channel for file storage
    vault_channel_id: int = 0

    # Inherit model_config from CommonSettings; no extra Config class needed


settings = Settings()
