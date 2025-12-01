"""
File cleanup module for anime-bot.

Provides background task for cleaning up old downloaded files by moving
them to archive or deleting them based on retention settings.
"""
import asyncio
import logging
import os
import time

from .config import settings

logger = logging.getLogger(__name__)

# Cleanup interval in seconds (1 hour)
CLEANUP_INTERVAL_SECONDS: int = 3600


async def cleanup_loop(stop_event: asyncio.Event) -> None:
    """Background task that periodically cleans up old downloaded files.

    Moves files older than the retention period to the archive directory,
    or deletes them if moving fails.

    Args:
        stop_event: Event to signal when the cleanup loop should stop.
    """
    download_dir = settings.download_dir
    archive_dir = settings.archive_dir
    os.makedirs(download_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)

    while not stop_event.is_set():
        now = time.time()
        try:
            for root, _dirs, files in os.walk(download_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        mtime = os.path.getmtime(fpath)
                    except Exception:
                        continue
                    age = now - mtime
                    if age >= settings.file_retention_seconds:
                        dest = os.path.join(archive_dir, fname)
                        try:
                            os.replace(fpath, dest)
                            logger.info("Moved %s to archive", fpath)
                        except Exception:
                            try:
                                os.remove(fpath)
                                logger.info("Deleted %s", fpath)
                            except Exception:
                                logger.exception("Failed to remove old file %s", fpath)
        except Exception:
            logger.exception("Error during cleanup")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CLEANUP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue
