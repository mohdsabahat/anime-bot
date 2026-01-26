"""
Download and upload task management for anime-bot.

This module provides the DownloadUploadTask class which handles the
download of anime episodes and their upload to Telegram.
"""
import asyncio
import logging
import os
import time
from typing import Callable, Optional, List

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from .constants import PROGRESS_UPDATE_INTERVAL
from .utils import take_screen_shot
from .downloader import AnimeDownloaderService, EpisodeDownloadResult
from .db import insert_uploaded_file
from .config import settings
from .uploader import Uploader

logger = logging.getLogger(__name__)


class DownloadUploadTask:
    """Task for downloading and uploading anime episodes.

    This class manages the complete workflow of downloading an episode
    from AnimePahe and uploading it to Telegram.

    Args:
        client: The Telegram client instance.
        anime_title: The title of the anime.
        anime_slug: The unique slug/session identifier for the anime.
        episodes: List of episode dicts with 'episode' (number) and 'session' (ep session id).
        chat_id: The Telegram chat ID to send updates to.
        uploader: The Uploader instance for uploading files.
        uploader_id: The user ID of the person who initiated the upload.
        quality: The preferred video quality (default: "360").
        audio: The preferred audio language (default: "jpn").
    """

    def __init__(
        self,
        client,
        anime_title: str,
        anime_slug: str,
        episodes: List[dict],
        chat_id: int,
        uploader: Uploader,
        uploader_id: int,
        quality: str = "360",
        audio: str = "jpn",
    ) -> None:
        """Initialize the download/upload task."""
        self.client = client
        self.anime_title = anime_title
        self.anime_slug = anime_slug
        self.episodes = episodes
        self.chat_id = chat_id
        self.uploader = uploader
        self.quality = quality
        self.audio = audio
        self.uploader_id = uploader_id
        self.downloader = AnimeDownloaderService()

    async def run(self, status_callback: Optional[Callable[[str], None]] = None) -> None:
        """Execute the download and upload task for all episodes.

        Args:
            status_callback: Optional callback function to report status updates.
        """

        async def status(msg: str) -> None:
            """Send status update via callback."""
            if status_callback:
                try:
                    await status_callback(msg)
                except Exception:
                    logger.debug("status callback failed")

        await status(f"Starting task: {self.anime_title} episodes {[ep['episode'] for ep in self.episodes]}")
        for ep_info in self.episodes:
            ep_num = int(ep_info["episode"])
            ep_session = ep_info["session"]
            await status(f"Preparing to download ep {ep_num} ...")
            logger.debug("tasks- qual: %s, audio: %s", self.quality, self.audio)
            res: EpisodeDownloadResult = await self.downloader.download_episode(
                self.anime_title, self.anime_slug, ep_session, ep_num,
                quality=self.quality, audio=self.audio
            )
            if not res.success:
                await status(f"Download failed ep {ep_num}: {res.reason}")
                # Respect rate limiting and continue
                await asyncio.sleep(settings.rate_limit_seconds)
                continue

            # Get metadata of video
            metadata = extractMetadata(createParser(res.filepath))
            duration = 0

            if metadata.has("duration"):
                duration = metadata.get("duration").seconds
            # Get ss for thumbnail
            thumb = await take_screen_shot(
                res.filepath, settings.download_dir, duration/2
            )

            # Upload result.filepath
            try:
                await status(f"Uploading ep {ep_num} ({os.path.basename(res.filepath)}) ...")

                # Improved progress callback with debouncing and percent threshold
                last_update = {"time": 0, "percent": 0}
                # progress callback factory
                def progress_cb(current: int, total: int, s_time: float) -> None:
                    """Non-blocking progress callback for upload status updates."""
                    cur_time = time.time()
                    percent = int((current / total) * 100) if total else 0
                    if (
                        (cur_time - last_update["time"] >= PROGRESS_UPDATE_INTERVAL)
                        and (percent - last_update["percent"] >= 5)
                    ) or percent == 100:
                        last_update["time"] = cur_time
                        last_update["percent"] = percent
                        try:
                            status(f"Uploading ep {ep_num}: {current // (1024 * 1024)}/{total // (1024 * 1024)} MB ({percent}%)")
                            # asyncio.create_task(
                            #     status(f"Uploading ep {ep_num}: {current // (1024 * 1024)}/{total // (1024 * 1024)} MB")
                            # )
                        except Exception:
                            pass

                # TODO: replace chat id with the id of person who uploaded
                caption = f"{self.anime_title} - Episode {ep_num}\n\nUploaded by: {self.chat_id}"
                start_time = time.time()
                msg = await self.uploader.upload_file(
                    settings.vault_channel_id,
                    res.filepath,
                    caption=caption,
                    progress_callback=lambda d, t: progress_cb(d, t, start_time),
                    thumbnail=thumb,
                )
                filesize = os.path.getsize(res.filepath) if os.path.exists(res.filepath) else None
                # insert DB
                try:
                    await insert_uploaded_file(self.anime_title, ep_num, msg.chat_id, self.uploader_id, res.episode_lang, 
                                               res.episode_qual, msg.id, os.path.basename(res.filepath), filesize
                                               )
                except Exception:
                    logger.exception("DB insert failed for %s Ep %s", self.anime_title, ep_num)

                await status(f"Uploaded ep {ep_num} successfully.")

            except Exception as e:
                logger.exception("Upload failed for ep %s", ep_num)
                await status(f"Upload failed for ep {ep_num}: {e}")

            # Remove thumbnail image
            try:
                os.remove(thumb)
            except Exception:
                logger.exception("Failed to delete thumbnail image %s", thumb)

            # optionally delete local file if configured
            if settings.delete_after_upload and res.filepath and os.path.exists(res.filepath):
                try:
                    os.remove(res.filepath)
                except Exception:
                    logger.exception("Failed to delete file %s", res.filepath)

            # Rate limit between episodes to avoid hammering animepahe
            await asyncio.sleep(settings.rate_limit_seconds)

        await status("Task finished.")
