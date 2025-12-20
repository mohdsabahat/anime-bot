"""
Logging configuration for anime-bot.

Provides centralized logging setup using the application settings.
"""
import logging
from logging import handlers

from .config import settings


def configure_logging() -> None:
    """Configure the logging system based on application settings."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = handlers.RotatingFileHandler(
        "anime_bot.log", maxBytes=1024 * 1024, backupCount=3
    )
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logging.basicConfig(
        level=level,
        handlers=[handler],
    )
