"""
File uploader module for anime-bot.

Provides asynchronous file upload functionality to Telegram with
concurrency control.
"""
import asyncio
import logging
from typing import Callable, Optional

from telethon import TelegramClient
from telethon.tl.custom.message import Message

logger = logging.getLogger(__name__)


class Uploader:
    """Handles file uploads to Telegram with concurrency control.

    Uses a semaphore to limit the number of concurrent uploads to avoid
    overwhelming the Telegram API.

    Args:
        client: The Telegram client instance.
        concurrency: Maximum number of concurrent uploads (default: 2).
    """

    def __init__(self, client: TelegramClient, concurrency: int = 2) -> None:
        """Initialize the uploader with concurrency control."""
        self.client = client
        self.semaphore = asyncio.Semaphore(concurrency)

    async def upload_file(
        self,
        dest_chat: int,
        file_path: str,
        thumbnail: str,
        caption: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> Message:
        """Upload a file to a Telegram chat.

        Args:
            dest_chat: The destination chat ID.
            file_path: Path to the file to upload.
            thumbnail: Path to the thumbnail image.
            caption: Optional caption for the file.
            progress_callback: Optional callback for upload progress.

        Returns:
            The sent message containing the uploaded file.
        """
        async with self.semaphore:
            msg = await self.client.send_file(
                dest_chat,
                file_path,
                caption=caption,
                progress_callback=progress_callback,
                supports_streaming=True,
                force_document=False,
                thumb=thumbnail,
            )
            return msg
