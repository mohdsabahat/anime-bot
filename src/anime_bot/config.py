from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv

# Load variables from the .env file
load_dotenv()

print(f'SECRET_KEY: {os.getenv("TG_API_ID")}')
print(f'DATABASE_URL: {os.getenv("TG_API_HASH")}')

class Settings(BaseSettings):
    tg_api_id: int
    tg_api_hash: str
    tg_bot_token: str

    database_url: str = "sqlite+aiosqlite:///./data/anime_files.db"
    download_dir: str = "./data/downloads"
    archive_dir: str = "./data/archive"

    max_upload_concurrency: int = 2
    download_workers: int = 2

    file_retention_seconds: int = 7 * 24 * 3600
    delete_after_upload: bool = True

    rate_limit_seconds: float = 1.0  # wait between episode downloads
    log_level: str = "INFO"
    vault_channel_id: int = 0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

_env = os.environ.copy()
settings = Settings(
    tg_api_id=int(_env.get("TG_API_ID", 0)),
    tg_api_hash=_env.get("TG_API_HASH", ""),
    tg_bot_token=_env.get("TG_BOT_TOKEN", ""),
    database_url=_env.get("DATABASE_URL", "sqlite+aiosqlite:///./data/anime_files.db"),
    download_dir=_env.get("DOWNLOAD_DIR", "./data/downloads"),
    archive_dir=_env.get("ARCHIVE_DIR", "./data/archive"),
    max_upload_concurrency=int(_env.get("MAX_UPLOAD_CONCURRENCY", "2")),
    download_workers=int(_env.get("DOWNLOAD_WORKERS", "2")),
    file_retention_seconds=int(_env.get("FILE_RETENTION_SECONDS", str(7*24*3600))),
    delete_after_upload=_env.get("DELETE_AFTER_UPLOAD", "true").lower() in ("1","true","yes"),
    rate_limit_seconds=float(_env.get("RATE_LIMIT_SECONDS", "1.0")),
    log_level=_env.get("LOG_LEVEL", "INFO"),
    vault_channel_id=_env.get("VAULT_CHANNEL_ID", 0)
)
