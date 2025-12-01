"""
Database models for anime-bot.

Defines SQLAlchemy ORM models for storing uploaded file metadata.
"""
from sqlalchemy import Column, Integer, String, BigInteger, TIMESTAMP
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class UploadedFile(Base):
    """Model for tracking uploaded anime episode files.

    Stores metadata about files that have been uploaded to Telegram,
    including episode information, chat IDs, and file details.
    """
    __tablename__ = 'uploaded_files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    anime_title = Column(String, nullable=False, index=True)
    episode = Column(Integer, nullable=False, index=True)
    uploaded_chat_id = Column(BigInteger, nullable=False)
    uploader_user_id = Column(BigInteger, nullable = False)
    uploaded_message_id = Column(BigInteger, nullable=False)
    vault_chat_id = Column(BigInteger, nullable=False)
    vault_message_id = Column(BigInteger, nullable=False)
    ep_lang = Column(String, nullable=False)
    ep_qual = Column(Integer, nullable=False)
    filename = Column(String, nullable=False)
    filesize = Column(BigInteger)
    created_at = Column(TIMESTAMP, server_default=func.now())
    # uploader_user_id INTEGER,
    #     vault_chat_id INTEGER,
    #     vault_message_id INTEGER,

    def __repr__(self):
        return f"<UploadedFile {self.anime_title} ep{self.episode} file={self.filename}>"
