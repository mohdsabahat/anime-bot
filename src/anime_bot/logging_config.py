"""
Logging configuration for anime-bot.

Provides centralized logging setup using the application settings.
"""
import logging

from .config import settings


def configure_logging() -> None:
    """Configure the logging system based on application settings."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
