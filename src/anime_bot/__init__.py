"""
Anime Bot - A Telegram bot for downloading and uploading anime episodes.

This package provides functionality to search for anime, download episodes
from AnimePahe, and upload them to Telegram.
"""
from .bot import client, main

__all__ = ["client", "main"]

# Import commands to register handlers (must be after client is defined)
from .commands import ping, list, start, track  # noqa: F401