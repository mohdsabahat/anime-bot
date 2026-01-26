"""
Uploaded files routes.

Provides endpoints for accessing uploaded file data.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..schemas import (
    UploadedFileResponse,
    UploadedFileListResponse,
    AnimeTitleListResponse,
    AnimeTitleItem,
    StatsResponse,
)

# Import the model from anime_bot
import sys
import os

# Add parent directory to path if needed for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from anime_bot.models import UploadedFile, Anime
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["Uploaded Files"])


@router.get("/", response_model=UploadedFileListResponse)
async def list_files(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    anime_title: Optional[str] = Query(None, description="Filter by anime title"),
    episode: Optional[int] = Query(None, ge=1, description="Filter by episode number"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> UploadedFileListResponse:
    """
    List uploaded files with pagination and optional filtering.

    Args:
        page: Page number (1-indexed).
        page_size: Number of items per page.
        anime_title: Optional filter by anime title.
        episode: Optional filter by episode number.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        UploadedFileListResponse: Paginated list of uploaded files.
    """
    # Build base query with join
    query = select(UploadedFile, Anime).join(Anime, UploadedFile.anime_id == Anime.id)
    count_query = select(func.count(UploadedFile.id)).join(Anime, UploadedFile.anime_id == Anime.id)

    # Apply filters
    if anime_title:
        query = query.where(Anime.title.ilike(f"%{anime_title}%"))
        count_query = count_query.where(Anime.title.ilike(f"%{anime_title}%"))
    if episode is not None:
        query = query.where(UploadedFile.episode == episode)
        count_query = count_query.where(UploadedFile.episode == episode)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = (
        query.order_by(UploadedFile.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    # Execute query
    result = await db.execute(query)
    rows = result.fetchall()

    # Build episode items with anime object
    episode_items = []
    for file, anime in rows:
        alt_titles = [t for t in anime.alt_titles.split('|') if t] if anime.alt_titles else []
        anime_item = AnimeTitleItem(id=anime.id, title=anime.title, alt_titles=alt_titles)
        episode_dict = file.__dict__.copy()
        episode_dict['anime'] = anime_item
        episode_items.append(UploadedFileResponse.model_validate(episode_dict))

    # Calculate has_next
    has_next = (page * page_size) < total

    return UploadedFileListResponse(
        items=episode_items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
    )


@router.get("/anime-titles", response_model=AnimeTitleListResponse)
async def list_anime_titles(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> AnimeTitleListResponse:
    """
    Get list of all unique anime titles.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        AnimeTitleListResponse: List of unique anime titles.
    """
    query = select(Anime).order_by(Anime.title)
    result = await db.execute(query)
    anime_rows = result.scalars().all()

    titles = []
    for anime in anime_rows:
        # Split alt_titles by '|' and filter out empty strings
        if anime.alt_titles:
            alt_titles = [t for t in anime.alt_titles.split('|') if t]
        else:
            alt_titles = []
        titles.append(AnimeTitleItem(
            id=anime.id,
            title=anime.title,
            alt_titles=alt_titles
        ))

    return AnimeTitleListResponse(titles=titles, total=len(titles))

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> StatsResponse:
    """
    Get database statistics.

    Args:
        db: Database session.
        current_user: Authenticated user.

    Returns:
        StatsResponse: Database statistics.
    """
    query = (
        select(
            func.count(UploadedFile.id).label("total_episodes"),
            func.count(func.distinct(Anime.id)).label("total_anime_titles"),
            func.coalesce(func.sum(UploadedFile.filesize), 0).label("total_size_bytes"),
        )
        .select_from(UploadedFile)
        .join(Anime, UploadedFile.anime_id == Anime.id, isouter=True)
    )

    result = await db.execute(query)
    total_episodes, total_anime_titles, total_size_bytes = result.one()

    return StatsResponse(
        total_files=total_episodes or 0,
        total_anime=total_anime_titles or 0,
        total_size_bytes=total_size_bytes or 0,
    )


@router.get("/{file_id}", response_model=UploadedFileResponse)
async def get_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> UploadedFileResponse:
    """
    Get a specific uploaded file by ID.

    Args:
        file_id: The file ID to retrieve.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        UploadedFileResponse: The uploaded file details.

    Raises:
        HTTPException: If file not found.
    """
    # Join UploadedFile and Anime
    query = (
        select(UploadedFile, Anime)
        .join(Anime, UploadedFile.anime_id == Anime.id)
        .where(UploadedFile.id == file_id)
    )
    result = await db.execute(query)
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id {file_id} not found",
        )

    file, anime = row

    # Handle alt_titles as list
    if anime and anime.alt_titles:
        alt_titles = [t for t in anime.alt_titles.split('|') if t]
    else:
        alt_titles = []

    anime_item = None
    if anime:
        anime_item = AnimeTitleItem(
            id=anime.id,
            title=anime.title,
            alt_titles=alt_titles
        )

    # Build response
    return UploadedFileResponse(
        id=file.id,
        anime_id=file.anime_id,
        anime_title=file.anime_title,
        episode=file.episode,
        uploaded_chat_id=file.uploaded_chat_id,
        uploader_user_id=file.uploader_user_id,
        uploaded_message_id=file.uploaded_message_id,
        vault_chat_id=file.vault_chat_id,
        vault_message_id=file.vault_message_id,
        ep_lang=file.ep_lang,
        ep_qual=file.ep_qual,
        filename=file.filename,
        filesize=file.filesize,
        created_at=file.created_at,
        anime=anime_item
    )


@router.get("/anime/{anime_id}/episodes", response_model=UploadedFileListResponse)
async def list_episodes_for_anime(
    anime_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> UploadedFileListResponse:
    """
    List all episodes for a specific anime.

    Args:
        anime_title: The anime title to filter by.
        page: Page number (1-indexed).
        page_size: Number of items per page.
        db: Database session.
        current_user: Authenticated user.

    Returns:
        UploadedFileListResponse: Paginated list of episodes.
    """
    # Fetch anime details
    anime_result = await db.execute(select(Anime).where(Anime.id == anime_id))
    anime = anime_result.scalar_one_or_none()
    if not anime:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Anime with id {anime_id} not found",
        )
    alt_titles = [t for t in anime.alt_titles.split('|') if t] if anime.alt_titles else []
    anime_item = AnimeTitleItem(id=anime.id, title=anime.title, alt_titles=alt_titles)

    # Query episodes
    query = select(UploadedFile).where(UploadedFile.anime_id == anime_id)
    count_query = select(func.count(UploadedFile.id)).where(UploadedFile.anime_id == anime_id)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(UploadedFile.episode.asc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    files = result.scalars().all()
    has_next = (page * page_size) < total

    return UploadedFileListResponse(
        items=[UploadedFileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
        anime=anime_item
    )
