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

async def consume_connect_token(token: str) -> str | None:
    """
    Atomically consume a connection token and return the session ID.
    Returns None if token is invalid or expired.
    """
    
    key = f"{settings.token_prefix}{token}"
    
    try:
        # GETDEL is atomic: get value and delete key in one operation
        # Available in Redis >= 6.2
        session_id = await RedisClient.getdel(key)
        return session_id
    except Redis.ResponseError:
        # Fallback for older Redis: use Lua script for atomicity
        lua_script = """
        local v = redis.call('GET', KEYS[1])
        if v then
            redis.call('DEL', KEYS[1])
        end
        return v
        """
        session_id = await RedisClient.eval(lua_script, 1, key)
        return session_id

async def link_chat_to_session(session_id: str, chat_id: int) -> None:
    """Link a Telegram chat_id to a browser session."""
    try:
        await RedisClient.set(f"{settings.session_chat_prefix}{session_id}", str(chat_id))
        logger.info(f"Linked session {session_id} to chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to link session {session_id} to chat {chat_id}: {e}")
        raise

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
        session_id = await consume_connect_token(token)
        if not session_id:
                await event.respond(
                    "⚠️ **Connection Failed**\n\n"
                    "This link has expired or was already used.\n"
                    "Please go back to the website and click 'Connect Telegram' again."
                )
                return
        
        # Link the chat to the session
        await link_chat_to_session(session_id, chat_id)

        await event.respond(
                "✅ **Connected Successfully!**\n\n"
                "Your Telegram is now linked to the website.\n"
                "Go back and the page will automatically redirect.\n\n"
                "💡 You can now receive anime episodes directly here!"
            )
    except Exception as e:
        logger.exception(f"Error linking start token: {e}")
        await event.respond(
            "⚠️ **Connection Failed**\n\n"
            "An unexpected error occurred while linking your Telegram.\n"
            "Please try again later."
        )