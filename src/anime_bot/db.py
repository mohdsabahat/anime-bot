"""
Database module for anime-bot.

Provides async database operations using SQLAlchemy for storing and
retrieving uploaded file records.
"""
import logging
import os

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from typing import Optional, List

from .config import settings
from .models import Base, UploadedFile

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    if settings.database_url.startswith("sqlite"):
        path = settings.database_url.split("///")[-1]
        parent = os.path.dirname(path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("DB initialized")


async def insert_uploaded_file(
    anime_title: str,
    episode: int,
    chat_id: int,
    uploader_id: int,
    ep_lang: str,
    ep_qual: int,
    message_id: int,
    filename: str,
    filesize: int,
) -> UploadedFile:
    """Insert a new uploaded file record into the database.

    Args:
        anime_title: The title of the anime.
        episode: The episode number.
        chat_id: The chat ID where the file was uploaded.
        uploader_id: The user ID of the uploader.
        ep_lang: The episode audio language.
        ep_qual: The episode quality.
        message_id: The Telegram message ID.
        filename: The name of the uploaded file.
        filesize: The size of the file in bytes.

    Returns:
        The created UploadedFile object.
    """
    async with AsyncSessionLocal() as session:
        obj = UploadedFile(
            anime_title=anime_title,
            episode=episode,
            uploaded_chat_id=chat_id,
            uploader_user_id=uploader_id,
            uploaded_message_id=message_id,
            vault_chat_id=chat_id,
            vault_message_id=message_id,
            ep_lang=ep_lang,
            ep_qual=ep_qual,
            filename=filename,
            filesize=filesize,
        )
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj


async def get_latest_uploaded(anime_title: str, episode: int) -> Optional[UploadedFile]:
    """Get the most recently uploaded file for a specific anime episode.

    Args:
        anime_title: The title of the anime.
        episode: The episode number.

    Returns:
        The UploadedFile object if found, None otherwise.
    """
    async with AsyncSessionLocal() as session:
        query = (
            select(UploadedFile)
            .where(UploadedFile.anime_title == anime_title, UploadedFile.episode == episode)
            .order_by(UploadedFile.created_at.desc())
            .limit(1)
        )
        res = await session.execute(query)
        return res.scalar_one_or_none()


async def list_uploaded_for_anime(anime_title: str, limit: int = 50) -> List[UploadedFile]:
    """List all uploaded files for a specific anime.

    Args:
        anime_title: The title of the anime.
        limit: Maximum number of results to return (default: 50).

    Returns:
        List of UploadedFile objects.
    """
    async with AsyncSessionLocal() as session:
        query = (
            select(UploadedFile)
            .where(UploadedFile.anime_title == anime_title)
            .order_by(UploadedFile.episode.asc())
            .limit(limit)
        )
        res = await session.execute(query)
        return res.scalars().all()


async def list_distinct_anime_titles() -> List[str]:
    """Get a list of all distinct anime titles in the database.

    Returns:
        List of unique anime titles.
    """
    async with AsyncSessionLocal() as session:
        query = select(UploadedFile.anime_title).distinct()
        res = await session.execute(query)
        return [r[0] for r in res.fetchall()]