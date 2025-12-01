"""
AnimePahe API client wrapper for anime-bot.

Provides async wrappers around the anime_downloader library for fetching
anime data, episodes, and managing downloads.
"""
import asyncio
import logging
from typing import List, Dict, Optional, Callable

logger = logging.getLogger(__name__)

# Provided API from docs
try:
    from anime_downloader.api import AnimePaheAPI
    from anime_downloader.downloader import Downloader
    from anime_downloader.async_downloader import download_episode_async
    from anime_downloader import config, config_manager
except Exception as exc:
    # if import fails we'll surface a helpful error when used
    AnimePaheAPI = None
    Downloader = None
    download_episode_async = None
    logger.warning("anime_downloader imports failed: %s", exc)


class AnimePaheClient:
    """Async wrapper for the AnimePahe API.

    Provides asynchronous methods for searching anime, fetching episodes,
    and downloading content from AnimePahe.

    Args:
        verify_ssl: Whether to verify SSL certificates (default: True).
    """

    def __init__(self, verify_ssl: bool = True) -> None:
        """Initialize the AnimePahe client."""
        if AnimePaheAPI is None:
            raise RuntimeError("anime_downloader.api.AnimePaheAPI not importable")
        app_config = config_manager.load_config()
        if "base_url" in app_config and app_config["base_url"] != config.BASE_URL:
            config.set_base_url(app_config["base_url"])
        self._api = AnimePaheAPI(verify_ssl=verify_ssl)

    async def search(self, query: str) -> List[Dict[str, str]]:
        """Search for anime by name.

        Args:
            query: The search query string.

        Returns:
            List of anime results with title and session info.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self._api.search(query))

    async def fetch_episodes(self, anime_name: str, anime_slug: str) -> List[Dict]:
        """Fetch all episodes for an anime.

        Args:
            anime_name: The name of the anime.
            anime_slug: The session/slug identifier.

        Returns:
            List of episode dicts with episode number and session.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: self._api.fetch_episode_data(anime_name, anime_slug)
        )

    async def get_stream_url(
        self,
        anime_slug: str,
        episode_session: str,
        quality: str = "720",
        audio: str = "jpn",
    ) -> Optional[str]:
        """Get the stream URL for an episode.

        Args:
            anime_slug: The anime session/slug.
            episode_session: The episode session identifier.
            quality: Preferred video quality (default: "720").
            audio: Preferred audio language (default: "jpn").

        Returns:
            Stream URL or None if not found.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._api.get_stream_url(
                anime_slug, episode_session, quality=quality, audio=audio
            ),
        )

    async def get_playlist_url(self, stream_url: str) -> Optional[str]:
        """Get the M3U8 playlist URL from a stream URL.

        Args:
            stream_url: The stream page URL.

        Returns:
            Playlist URL or None if not found.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self._api.get_playlist_url(stream_url))

    async def download_playlist(self, playlist_url: str, output_dir: str) -> Optional[str]:
        """Download a playlist file.

        Args:
            playlist_url: URL of the M3U8 playlist.
            output_dir: Directory to save the playlist.

        Returns:
            Path to the downloaded playlist file or None.
        """
        if Downloader is None:
            raise RuntimeError("Downloader not available")
        downloader = Downloader(self._api)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: downloader.fetch_playlist(playlist_url, output_dir)
        )

    async def download_from_playlist(self, playlist_path: str, num_threads: int = 50) -> bool:
        """Download video segments from a playlist file.

        Args:
            playlist_path: Path to the local M3U8 playlist file.
            num_threads: Number of concurrent download threads (default: 50).

        Returns:
            True if download was successful.
        """
        if Downloader is None:
            raise RuntimeError("Downloader not available")
        downloader = Downloader(self._api)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: downloader.download_from_playlist_cli(playlist_path, num_threads)
        )

    async def compile_video(
        self,
        segment_dir: str,
        output_path: str,
        progress_callback: Optional[Callable] = None,
    ) -> bool:
        """Compile video segments into a single file.

        Args:
            segment_dir: Directory containing video segments.
            output_path: Path for the output video file.
            progress_callback: Optional callback for progress updates.

        Returns:
            True if compilation was successful.
        """
        if Downloader is None:
            raise RuntimeError("Downloader not available")
        downloader = Downloader(self._api)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: downloader.compile_video(segment_dir, output_path, progress_callback)
        )
