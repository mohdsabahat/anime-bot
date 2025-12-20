"""
Search API routes module.

Provides endpoints for searching anime titles and uploaded files.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from anime_bot.models import UploadedFile

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Search Titles"])

@router.get("/", response_model=List[str])
async def search_titles(
    query: str = Query(..., min_length=1, description="Search query for anime titles"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results to return"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user),
) -> List[str]:
    """
    Search for anime titles matching the query string.

    Args:
        query: The search query string.
        limit: Maximum number of results to return.
        db: Database session.
    Returns:
        List of matching anime titles.
    """
    try:
        stmt = select(UploadedFile.anime_title).where(UploadedFile.anime_title.ilike(f"%{query}%")).distinct().limit(limit)
        result = await db.execute(stmt)
        titles = [row[0] for row in result.fetchall()]
        logger.debug(f"Search query: {query}, Results found: {len(titles)}")
        return titles
    except Exception as e:
        logger.error(f"Error searching titles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while searching for titles."
        )