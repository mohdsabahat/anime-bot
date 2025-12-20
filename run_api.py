"""
API server entry point.

Run this script to start the FastAPI server.
"""
import uvicorn
from src.api.config import api_settings
from src.api.main import run_server

if __name__ == "__main__":
    # uvicorn.run(
    #     "src.api.main:app",
    #     host=api_settings.api_host,
    #     port=api_settings.api_port,
    #     reload=False,
    #     log_level="info",
    # )
    run_server()
