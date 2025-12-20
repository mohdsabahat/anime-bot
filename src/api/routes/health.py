"""
Health check routes.

Provides endpoints for API health monitoring.
"""
from fastapi import APIRouter

from ..schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse: API health status.
    """
    return HealthResponse(status="healthy", version="1.0.0")


@router.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """
    Root endpoint.

    Returns:
        HealthResponse: API health status.
    """
    return HealthResponse(status="healthy", version="1.0.0")
