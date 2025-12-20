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
    StatsResponse,
)

# Import the model from anime_bot
import sys
import os

# Add parent directory to path if needed for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from anime_bot.models import UploadedFile
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
    # Build base query
    query = select(UploadedFile)
    count_query = select(func.count(UploadedFile.id))

    # Apply filters
    if anime_title:
        query = query.where(UploadedFile.anime_title.ilike(f"%{anime_title}%"))
        count_query = count_query.where(
            UploadedFile.anime_title.ilike(f"%{anime_title}%")
        )
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
    files = result.scalars().all()

    # Calculate has_next
    has_next = (page * page_size) < total

    return UploadedFileListResponse(
        items=[UploadedFileResponse.model_validate(f) for f in files],
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
    query = select(UploadedFile.anime_title).distinct().order_by(UploadedFile.anime_title)
    result = await db.execute(query)
    titles = [row[0] for row in result.fetchall()]

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
    # Total files
    total_files_result = await db.execute(select(func.count(UploadedFile.id)))
    total_files = total_files_result.scalar() or 0

    # Total unique anime
    total_anime_result = await db.execute(
        select(func.count(func.distinct(UploadedFile.anime_title)))
    )
    total_anime = total_anime_result.scalar() or 0

    # Total size
    total_size_result = await db.execute(
        select(func.coalesce(func.sum(UploadedFile.filesize), 0))
    )
    total_size = total_size_result.scalar() or 0

    return StatsResponse(
        total_files=total_files,
        total_anime=total_anime,
        total_size_bytes=total_size,
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
    query = select(UploadedFile).where(UploadedFile.id == file_id)
    result = await db.execute(query)
    file = result.scalar_one_or_none()

    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id {file_id} not found",
        )

    return UploadedFileResponse.model_validate(file)


@router.get("/anime/{anime_title}/episodes", response_model=UploadedFileListResponse)
async def list_episodes_for_anime(
    anime_title: str,
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
    # Build queries
    query = select(UploadedFile).where(UploadedFile.anime_title == anime_title)
    # Log the query string for debugging
    logger.info(f"SQL Query: {str(query)}")
    count_query = select(func.count(UploadedFile.id)).where(
        UploadedFile.anime_title == anime_title
    )

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(UploadedFile.episode.asc()).offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    files = result.scalars().all()

    # Calculate has_next
    has_next = (page * page_size) < total

    return UploadedFileListResponse(
        items=[UploadedFileResponse.model_validate(f) for f in files],
        total=total,
        page=page,
        page_size=page_size,
        has_next=has_next,
    )
