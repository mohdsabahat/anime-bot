"""
Start command for the anime bot.

Handles the /start command to welcome users.
"""

from telethon import events

from ..bot import client
from ..config import settings
from redis.asyncio import Redis
from ..redis_client import RedisClient
import logging

logger = logging.getLogger(__name__)

async def consume_connect_token(token: str, user_id: str) -> str | None:
    """
    Atomically consume a connection token and return the session ID.
    Returns None if token is invalid or expired.
    """
    
    key = f"{settings.token_prefix}{token}"
    
    try:
        logger.info(f"Searching for key: {key} to link user_id {user_id}")
        saved_token_id = await RedisClient.get(key)
        if not saved_token_id:
            # Token is not updated yet
            logger.info(f"Token {token} not found, set user_id {user_id} for future consumption.")
        await RedisClient.set(key, user_id)
        logger.info(f"Token {token} consumed, linked to user_id {user_id}.")
        return saved_token_id
    except Redis.ResponseError:
        return None

@client.on(events.NewMessage(pattern=r"^/start(?:\s+(.+))?"))
async def start_handler(event: events.NewMessage.Event) -> None:
    """
    Handle the /start command.
    Usage:
        - /start         → Welcome message
        - /start <token> → Link browser session to this chat
    """
    chat_id = event.chat_id

    # Extract token from command arguments
    match = event.pattern_match
    token = match.group(1).strip() if match.group(1) else None

    if not token:
        # No token provided - just a regular /start command
        await event.reply(
            "Hello — send `/search <anime name>` to search for anime. "
            "After selecting an anime send an episode list like `1-3` or use `/download <slug> <spec>`."
        )
        return
    
    # Token provided - link browser session
    logger.info(f"Linking browser session for chat_id={chat_id} with token={token}")

    try:
        saved_token_id = await consume_connect_token(token, user_id=str(chat_id))
        if not saved_token_id:
                await event.respond(
                    "⚠️ **Connection Failed**\n\n"
                    "This link has expired or was already used.\n"
                    "Please go back to the website and click 'Connect Telegram' again."
                )
                return
        respond = await event.respond(
            "✅ **Connected Successfully**\n\n"
            "Your Telegram has been linked to your browser session.\n"
            "You can now receive download links and notifications here."
        )
    except Exception as e:
        logger.exception(f"Error linking start token: {e}")
        await event.respond(
            "⚠️ **Connection Failed**\n\n"
            "An unexpected error occurred while linking your Telegram.\n"
            "Please try again later."
        )