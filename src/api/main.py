"""
FastAPI application entry point.

Creates and configures the FastAPI application with all routes,
middleware, and exception handlers.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import api_settings
from .routes import auth, files, health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting API server...")
    logger.info(f"Database URL: {api_settings.database_url}")
    yield
    # Shutdown
    logger.info("Shutting down API server...")


# Create FastAPI application
app = FastAPI(
    title="Anime Bot API",
    description="REST API for accessing anime-bot uploaded file data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS
cors_origins = api_settings.cors_origins.split(",") if api_settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "status_code": 500},
    )


# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(files.router)


def run_server() -> None:
    """Run the API server using uvicorn."""
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=api_settings.api_host,
        port=api_settings.api_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    run_server()
