"""
API configuration module.

Extends the base anime-bot settings with API-specific configuration.
"""
from pydantic_settings import BaseSettings
from typing import Optional
from src.config import CommonSettings


class APISettings(CommonSettings):
    """API-specific settings loaded from environment variables."""

    # API Server settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Authentication
    api_secret_key: str = "change-this-secret-key-in-production"
    api_token_expire_minutes: int = 30
    api_username: str = "admin"
    api_password: str = "admin"

    # CORS settings
    cors_origins: str = "*"

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Inherit model_config from CommonSettings; no extra Config class needed


api_settings = APISettings()
