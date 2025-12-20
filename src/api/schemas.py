"""
Pydantic schemas for API request/response models.

Defines data transfer objects for the API endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class Token(BaseModel):
    """Token response schema."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload data."""

    username: Optional[str] = None


class UploadedFileResponse(BaseModel):
    """Response schema for a single uploaded file."""

    id: int
    anime_title: str
    episode: int
    uploaded_chat_id: int
    uploader_user_id: int
    uploaded_message_id: int
    vault_chat_id: int
    vault_message_id: int
    ep_lang: str
    ep_qual: int
    filename: str
    filesize: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        """Pydantic config for ORM mode."""

        from_attributes = True


class UploadedFileListResponse(BaseModel):
    """Response schema for a list of uploaded files."""

    items: List[UploadedFileResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class AnimeTitleListResponse(BaseModel):
    """Response schema for list of anime titles."""

    titles: List[str]
    total: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "1.0.0"


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str
    status_code: int


class StatsResponse(BaseModel):
    """Statistics response schema."""

    total_files: int
    total_anime: int
    total_size_bytes: int
