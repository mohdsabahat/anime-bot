"""
Redis client module for Anime Bot.

Provides a Redis client instance for caching and session management.
"""

from redis.asyncio import Redis
from .config import settings

RedisClient = Redis.from_url(
    url=settings.redis_url,
    decode_responses=True,
    max_connections=5,
)