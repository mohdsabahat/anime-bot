import re
from typing import List, Dict
from anime_downloader import config
from .anime_api import AnimePaheClient
import asyncio
import json
import logging
import datetime
from pathlib import Path
import time
import os

logger = logging.getLogger(__name__)

EP_SPEC_RE = re.compile(r"^\d+(-\d+)?(,\d+(-\d+)?)*$")

def validate_episode_spec(spec: str) -> bool:
    return bool(EP_SPEC_RE.match(spec.strip()))

def expand_episode_spec_to_list(spec: str) -> List[int]:
    parts = [p.strip() for p in spec.split(',') if p.strip()]
    eps = set()
    for p in parts:
        if '-' in p:
            a, b = p.split('-', 1)
            for i in range(int(a), int(b) + 1):
                eps.add(i)
        else:
            eps.add(int(p))
    return sorted(eps)

def pick_episodes_from_episode_list(available_eps: List[Dict], desired_numbers: List[int]) -> List[Dict]:
    """
    available_eps is list of dicts: {'episode': '1', 'session': 'ep-session'}
    desired_numbers are ints; returns list of matched episode dicts in the same order as desired_numbers
    """
    index = {int(e['episode']): e for e in available_eps}
    result = []
    for n in desired_numbers:
        if n in index:
            result.append(index[n])
    return result

async def load_from_cache(api: AnimePaheClient) -> List[Dict]:
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
    
def fuzzy_score(title, query):
    """Basic fuzzy scoring without external libraries."""
    title = title.lower()
    query = query.lower()

    # Exact substring → best score
    if query in title:
        return 1000 - (title.index(query) * 2)

    # Fuzzy sequence match
    score = 0
    ti = 0
    for q in query:
        pos = title.find(q, ti)
        if pos == -1:
            return 0  # character missing → bad match
        score += 10
        ti = pos + 1
    return score

async def run_command(command: List[str]):
    process = await asyncio.create_subprocess_exec(
        *command,
        # stdout must a pipe to be accessible as process.stdout
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()
    e_response: str = stderr.decode().strip()
    t_response: str = stdout.decode().strip()
    print(e_response)
    print(t_response)
    return t_response, e_response

async def take_screen_shot(video_file, output_directory, ttl):
    # https://stackoverflow.com/a/13891070/4723940
    out_put_file_name = output_directory + "/" + str(time.time()) + ".jpg"
    file_genertor_command = [
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
    t_response, e_response = await run_command(file_genertor_command)
    if os.path.lexists(out_put_file_name):
        return out_put_file_name
    logger.info(e_response)
    logger.info(t_response)
    return None