\"\"\"
Utility functions for anime-bot.

Provides helper functions for episode specification parsing, fuzzy search,
cache management, and video processing.
\"\"\"
import asyncio
import datetime
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Dict

from anime_downloader import config

from .anime_api import AnimePaheClient
from .constants import EXACT_MATCH_SCORE, POSITION_PENALTY, CHAR_MATCH_SCORE

logger = logging.getLogger(__name__)

EP_SPEC_RE = re.compile(r\"^\\d+(-\\d+)?(,\\d+(-\\d+)?)*$\")

def validate_episode_spec(spec: str) -> bool:
    """Validate an episode specification string.

    Args:
        spec: The episode specification (e.g., "1", "1-3", "1,3,5-7").

    Returns:
        True if the specification is valid, False otherwise.
    """
    return bool(EP_SPEC_RE.match(spec.strip()))


def expand_episode_spec_to_list(spec: str) -> List[int]:
    """Expand an episode specification into a sorted list of episode numbers.

    Args:
        spec: The episode specification (e.g., "1-3,5" -> [1, 2, 3, 5]).

    Returns:
        Sorted list of episode numbers.
    """
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    eps = set()
    for part in parts:
        if "-" in part:
            start, end = part.split("-", 1)
            for i in range(int(start), int(end) + 1):
                eps.add(i)
        else:
            eps.add(int(part))
    return sorted(eps)


def pick_episodes_from_episode_list(
    available_eps: List[Dict], desired_numbers: List[int]
) -> List[Dict]:
    """Filter available episodes to only include desired episode numbers.

    Args:
        available_eps: List of episode dicts with 'episode' and 'session' keys.
        desired_numbers: List of episode numbers to select.

    Returns:
        List of matched episode dicts in the order of desired_numbers.
    """
    index = {int(ep["episode"]): ep for ep in available_eps}
    result = []
    for num in desired_numbers:
        if num in index:
            result.append(index[num])
    return result


async def load_from_cache(api: AnimePaheClient) -> List[Dict]:
    """Load the anime list from the cache file.

    If the cache file does not exist or is older than 1 day, requests the API
    client to refresh the cache.

    Args:
        api: The AnimePaheClient instance.

    Returns:
        List of anime dicts with 'session' and 'title' keys.
    """
#     animes = []
#     # first check if cache list is fresh enough (not old than 1 day) otherwise download cache list
# #    1. check if fresh
#     #00load  to animes
#     # 2. not fresh cache
#     # download fresh cache
#     await api.download_anime_list_cache()
    
#     animes = # load from cache config.ANIME_LIST_CACHE_FILE

#     return animes
    """
    Load the anime list from the cache file configured in config.ANIME_LIST_CACHE_FILE.

    Behavior:
    - If the cache file does not exist or is older than 1 day, request the API client
      to refresh the cache via api.download_anime_list_cache().
    - Load and return the JSON array from the cache file as a list[dict].
    - On any error, log and return an empty list.

    The file IO is executed in a threadpool to avoid blocking the event loop.
    """
    cache_path = Path(config.ANIME_LIST_CACHE_FILE)
    freshness_threshold = datetime.timedelta(days=1)

    def _is_fresh(path: Path) -> bool:
        try:
            if not path.exists():
                return False
            mtime = datetime.datetime.fromtimestamp(path.stat().st_mtime)
            return (datetime.datetime.now() - mtime) <= freshness_threshold
        except Exception:
            return False

    loop = asyncio.get_running_loop()

    try:
        if not _is_fresh(cache_path):
            # Attempt to refresh cache; let any exceptions surface to be handled below
            loop = asyncio.get_running_loop()
            logger.info("Updating anime cache!!")
            await loop.run_in_executor(None, lambda: api._api.download_anime_list_cache)
            # await api.download_anime_list_cache()

        if not cache_path.exists():
            logger.warning("Anime list cache does not exist at %s", cache_path)
            return []

        def _read_cache() -> List[Dict]:
            results = []
            with cache_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    slug, title = line.strip().split("::::", 1)
                    results.append({"session": slug, "title": title})
            if results == []:
                raise ValueError("Cache file is empty")
            return results

        animes = await loop.run_in_executor(None, _read_cache)
        return animes
    except Exception as exc:
        logger.exception("Failed to load anime list cache: %s", exc)
        return []
    
def fuzzy_score(title: str, query: str) -> int:
    """Calculate a fuzzy match score between a title and query.

    Uses a simple scoring algorithm without external libraries.

    Args:
        title: The title to match against.
        query: The search query.

    Returns:
        Score indicating match quality (higher is better, 0 means no match).
    """
    title = title.lower()
    query = query.lower()

    # Exact substring → best score
    if query in title:
        return EXACT_MATCH_SCORE - (title.index(query) * POSITION_PENALTY)

    # Fuzzy sequence match
    score = 0
    ti = 0
    for char in query:
        pos = title.find(char, ti)
        if pos == -1:
            return 0  # character missing → bad match
        score += CHAR_MATCH_SCORE
        ti = pos + 1
    return score


async def run_command(command: List[str]) -> tuple:
    """Run a shell command asynchronously and capture output.

    Args:
        command: List of command arguments to execute.

    Returns:
        Tuple of (stdout, stderr) as strings.
    """
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()
    e_response: str = stderr.decode().strip()
    t_response: str = stdout.decode().strip()
    logger.debug("Command stderr: %s", e_response)
    logger.debug("Command stdout: %s", t_response)
    return t_response, e_response


async def take_screen_shot(
    video_file: str, output_directory: str, ttl: float
) -> str | None:
    """Extract a screenshot from a video file using ffmpeg.

    Args:
        video_file: Path to the video file.
        output_directory: Directory to save the screenshot.
        ttl: Time position in seconds to take the screenshot.

    Returns:
        Path to the screenshot file, or None if extraction failed.
    """
    # https://stackoverflow.com/a/13891070/4723940
    out_put_file_name = output_directory + "/" + str(time.time()) + ".jpg"
    file_generator_command = [
        "ffmpeg",
        "-ss",
        str(ttl),
        "-i",
        video_file,
        "-vframes",
        "1",
        out_put_file_name,
    ]
    # width = "90"
    t_response, e_response = await run_command(file_generator_command)
    if os.path.lexists(out_put_file_name):
        return out_put_file_name
    logger.info(e_response)
    logger.info(t_response)
    return None