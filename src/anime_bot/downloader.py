import asyncio, os, shutil, logging, tempfile
from typing import Optional, List, Dict, Any
from .anime_api import AnimePaheClient
from .config import settings
from anime_downloader import config as AnimepaheConfig 
from bs4 import BeautifulSoup
from .logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

# try to import the async helper if available
try:
    # from anime_downloader.async_downloader import download_episode_async
    download_episode_async = None
except Exception:
    download_episode_async = None

class EpisodeDownloadResult:
    def __init__(self, episode_number:int, episode_qual:int, episode_lang:str, filepath:Optional[str], success:bool, reason:Optional[str]=None):
        self.episode = episode_number
        self.episode_qual = episode_qual
        self.episode_lang = episode_lang
        self.filepath = filepath
        self.success = success
        self.reason = reason

class AnimeDownloaderService:
    def __init__(self):
        self.client = AnimePaheClient(verify_ssl=True)
        os.makedirs(settings.download_dir, exist_ok=True)

    async def get_stream_qualities(self, anime_slug: str, ep_session: str) -> List[Dict[str,str]]:
        """
        patch of the animepahe-dl library to fetch url's for all episode quality
        """
        
        play_url = f"{AnimepaheConfig.PLAY_URL}/{anime_slug}/{ep_session}"
        response = self.client._api._request(play_url)
        if not response:
            logger.error("Failed to get episode page.")
            return None
        soup = BeautifulSoup(response.data, "html.parser")
        buttons = soup.find_all("button", attrs={"data-src": True, "data-av1": "0"})

        # Extract only the primitive values we need into plain Python dicts
        streams: List[Dict[str, Any]] = []
        for b in buttons:
            streams.append(
                {
                    "quality": b.get("data-resolution") or "0",
                    "audio": b.get("data-audio") or None,
                    "url": b.get("data-src") or None,
                }
            )
        
        if not streams:
            logger.warning("No streams found on the page.")
            return None
        
        # Log available streams for debugging
        available_streams_str = ", ".join(
            [f"{s['quality']}p ({s['audio']})" for s in streams if s.get("quality")]
        )
        logger.info(f"Available streams: {available_streams_str}")

        for s in streams:
            q_raw = s.get("quality")
            try:
                s["quality_val"] = int(q_raw) if q_raw is not None else 0
            except (ValueError, TypeError):
                s["quality_val"] = 0

        # Sort streams by quality ascending
        streams.sort(key=lambda s: int(s.get("quality_val", 0)))
        
        return streams

    async def download_episode(self, anime_title:str, anime_slug:str, ep_session:str, episode_number:int, quality:str="720", audio:str="jpn") -> EpisodeDownloadResult:
        """
        1) Get stream URL
        2) Get playlist (m3u8)
        3) Download segments (prefer async function if available)
        4) Compile into mp4
        Returns EpisodeDownloadResult with local file path or failure
        """
        try:
            # TODO: Add a condition to pass stream url in query params and skip fetching the episode page here if passed.
            # stream_url = await self.client.get_stream_url(anime_slug, ep_session, quality=quality, audio=audio)
            streams = await self.get_stream_qualities(anime_slug, ep_session)

            # logic to select quality automatically
            # --- Audio Selection ---
            audio_streams = [s for s in streams if s.get("audio") == audio]
            if not audio_streams:
                logger.warning(
                    f"Audio '{audio}' not found. Selecting from available audio languages."
                )
                audio_streams = streams  # Fallback to all streams
            
            # --- Quality Selection ---
            selected_stream = None
            stream_qual = None
            stream_lang = None
            try:
                print(f"dowbloader: {quality}")
                target_quality = int(quality)
                # Find best match: exact or next best available
                for stream in audio_streams:
                    if int(stream.get("quality_val", 0)) >= target_quality:
                        selected_stream = stream
                        stream_qual = int(stream.get("quality_val", 0))
                        stream_lang = stream.get('audio', '')
                        break
                # If no stream is >= target, pick the best available (last in sorted list)
                if not selected_stream and audio_streams:
                    selected_stream = audio_streams[-1]
                    logger.warning(
                        f"Quality '{quality}p' not found. "
                        f"Selected next best available: {selected_stream['quality']}p."
                    )
            except ValueError:
                logger.error(
                    f"Invalid quality specified: '{quality}'. Please use a number like '720'."
                )
                return None

            if not selected_stream:
                return EpisodeDownloadResult(episode_number, 0, stream_lang, None, False, "No stream URL")

            stream_url = selected_stream.get('url', None)
            playlist_url = await self.client.get_playlist_url(stream_url)
            if not playlist_url:
                return EpisodeDownloadResult(episode_number, 0, stream_lang, None, False, "No playlist URL")

            # create a temporary working dir per episode
            tmpdir = tempfile.mkdtemp(prefix=f"ep_{episode_number}_")
            try:
                playlist_path = await self.client.download_playlist(playlist_url, tmpdir)
                if not playlist_path:
                    return EpisodeDownloadResult(episode_number, 0, stream_lang, None, False, "Failed to fetch playlist")

                # prefer async downloader if available
                if download_episode_async is not None:
                    # parse playlist to get segments etc or rely on helper
                    success = await download_episode_async(
                        segments=None,  # docs example uses segments, but helper may accept playlist_path; we attempt to call with playlist_path pattern if helper supports - fallback to blocking below
                        key=None,
                        media_sequence=0,
                        output_dir=tmpdir,
                        max_concurrent=50
                    )
                    # if helper didn't accept None, this call may fail; So fallback to blocking below
                    if not success:
                        # fallback to blocking download_from_playlist_cli
                        success = await self.client.download_from_playlist(playlist_path, num_threads=50)
                else:
                    # blocking download using downloader (run in executor)
                    success = await self.client.download_from_playlist(playlist_path, num_threads=50)

                if not success:
                    return EpisodeDownloadResult(episode_number, 0, stream_lang, None, False, "Failed to download segments")

                # compile into an mp4 file
                out_filename = f"{anime_title.replace('/', '_')}_ep{episode_number}.mp4"
                output_path = os.path.join(settings.download_dir, out_filename)
                compiled = await self.client.compile_video(tmpdir, output_path, progress_callback=None)
                if not compiled:
                    # maybe the download produced a single file already - check tmpdir for mp4
                    mp4s = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(('.mp4','.mkv'))]
                    if mp4s:
                        # move first found
                        shutil.move(mp4s[0], output_path)
                        compiled = True
                if not compiled:
                    return EpisodeDownloadResult(episode_number, 0, stream_lang, None, False, "Failed to compile video")

                return EpisodeDownloadResult(episode_number, stream_qual, stream_lang, output_path, True, None)
            finally:
                # remove temp dir after compilation unless debugging (we already moved file)
                try:
                    if os.path.exists(tmpdir):
                        shutil.rmtree(tmpdir, ignore_errors=True)
                except Exception:
                    logger.exception("cleanup tmpdir failed")
        except Exception as e:
            logger.exception("download_episode error")
            return EpisodeDownloadResult(episode_number, 0, stream_lang, None, False, str(e))
