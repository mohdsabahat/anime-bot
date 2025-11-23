import asyncio, os, logging
from typing import Callable, Optional, List

from .utils import take_screen_shot
from .downloader import AnimeDownloaderService, EpisodeDownloadResult
from .db import insert_uploaded_file
from .config import settings
from .uploader import Uploader  # we'll create uploader in bot and pass in
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
import time

logger = logging.getLogger(__name__)

class DownloadUploadTask:
    def __init__(self, client, anime_title:str, anime_slug:str, episodes:List[dict], chat_id:int, uploader:Uploader, uploader_id: int, quality:str="360", audio:str="jpn"):
        """
        episodes: list of dicts with keys 'episode' (number) and 'session' (ep session id)
        """
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

    async def run(self, status_callback: Optional[Callable[[str], None]] = None):
        async def status(msg:str):
            if status_callback:
                try:
                    await status_callback(msg)
                except Exception:
                    logger.debug("status callback failed")

        await status(f"Starting task: {self.anime_title} episodes {[e['episode'] for e in self.episodes]}")
        for ep_info in self.episodes:
            ep_num = int(ep_info['episode'])
            ep_session = ep_info['session']
            await status(f"Preparing to download ep {ep_num} ...")
            print(f"tasks- qual: {self.quality}, audio: {self.audio}")
            res: EpisodeDownloadResult = await self.downloader.download_episode(self.anime_title, self.anime_slug, ep_session, ep_num, quality=self.quality, audio=self.audio)
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
                # progress callback factory
                start_time = time.time()
                def progress_cb(current, total):
                    # schedule updates; non-blocking
                    cur_time = time.time()
                    if (cur_time - start_time) < 5:
                        return
                    start_time = cur_time
                    try:
                        asyncio.create_task(status(f"Uploading ep {ep_num}: {current//(1024*1024)}/{total//(1024*1024)} MB"))
                    except Exception:
                        pass

                # TODO: replace chat id with the id of person who uploaded 
                caption = f"{self.anime_title} - Episode {ep_num}\n\nUploaded by: {self.chat_id}"
                msg = await self.uploader.upload_file(settings.vault_channel_id, res.filepath, caption=caption, 
                                                      progress_callback=progress_cb, thumbnail=thumb
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
