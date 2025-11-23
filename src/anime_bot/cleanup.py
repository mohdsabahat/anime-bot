import asyncio, os, time, logging
from .config import settings

logger = logging.getLogger(__name__)

async def cleanup_loop(stop_event: asyncio.Event):
    interval = 3600
    download_dir = settings.download_dir
    archive_dir = settings.archive_dir
    os.makedirs(download_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)

    while not stop_event.is_set():
        now = time.time()
        try:
            for root, dirs, files in os.walk(download_dir):
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
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            continue
