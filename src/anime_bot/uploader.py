import asyncio
from telethon import TelegramClient
from telethon.tl.custom.message import Message
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)

class Uploader:
    def __init__(self, client: TelegramClient, concurrency: int = 2):
        self.client = client
        self.semaphore = asyncio.Semaphore(concurrency)

    async def upload_file(self, dest_chat: int, file_path: str, thumbnail: str, caption: Optional[str] = None, progress_callback: Optional[Callable] = None) -> Message:
        await self.semaphore.acquire()
        try:
            msg = await self.client.send_file(dest_chat, file_path, caption=caption, 
                                              progress_callback=progress_callback, supports_streaming=True,
                                              force_document=False, thumb=thumbnail
                                              )
            return msg
        finally:
            self.semaphore.release()
