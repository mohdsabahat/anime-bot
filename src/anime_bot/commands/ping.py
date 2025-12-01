"""
Ping command handler for anime-bot.

Provides a simple health check command to verify the bot is responsive.
"""
from telethon import events

from ..bot import client


@client.on(events.NewMessage(pattern=r"^/ping"))
async def ping_handler(event: events.NewMessage.Event) -> None:
    """Handle the /ping command to check bot responsiveness."""
    await event.reply("PONG")