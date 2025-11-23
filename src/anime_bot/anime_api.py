import asyncio
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Provided API from docs
try:
    from anime_downloader.api import AnimePaheAPI  # The API client class from docs
    from anime_downloader.downloader import Downloader
    from anime_downloader.async_downloader import download_episode_async
    from anime_downloader import config, config_manager
except Exception as e:
    # if import fails we'll surface a helpful error when used
    AnimePaheAPI = None
    Downloader = None
    download_episode_async = None
    logger.warning("anime_downloader imports failed: %s", e)

class AnimePaheClient:
    def __init__(self, verify_ssl: bool = True):
        if AnimePaheAPI is None:
            raise RuntimeError("anime_downloader.api.AnimePaheAPI not importable")
        app_config = config_manager.load_config()
        if "base_url" in app_config and app_config["base_url"] != config.BASE_URL:
            config.set_base_url(app_config["base_url"])
        self._api = AnimePaheAPI(verify_ssl=verify_ssl)

    async def search(self, query: str) -> List[Dict[str,str]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self._api.search(query))

    async def fetch_episodes(self, anime_name: str, anime_slug: str) -> List[Dict]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self._api.fetch_episode_data(anime_name, anime_slug))

    async def get_stream_url(self, anime_slug: str, episode_session: str, quality: str = "720", audio: str = "jpn") -> Optional[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self._api.get_stream_url(anime_slug, episode_session, quality=quality, audio=audio))

    async def get_playlist_url(self, stream_url: str) -> Optional[str]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self._api.get_playlist_url(stream_url))

    async def download_playlist(self, playlist_url: str, output_dir: str) -> Optional[str]:
        # uses Downloader.fetch_playlist
        if Downloader is None:
            raise RuntimeError("Downloader not available")
        downloader = Downloader(self._api)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: downloader.fetch_playlist(playlist_url, output_dir))

    async def download_from_playlist(self, playlist_path: str, num_threads: int = 50) -> bool:
        # blocking method from docs - run in executor
        if Downloader is None:
            raise RuntimeError("Downloader not available")
        downloader = Downloader(self._api)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: downloader.download_from_playlist_cli(playlist_path, num_threads))

    async def compile_video(self, segment_dir: str, output_path: str, progress_callback=None) -> bool:
        if Downloader is None:
            raise RuntimeError("Downloader not available")
        downloader = Downloader(self._api)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: downloader.compile_video(segment_dir, output_path, progress_callback))
