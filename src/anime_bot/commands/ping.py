from ..bot import client
from telethon import events

@client.on(events.NewMessage(pattern=r"^/ping"))
async def start_c(e):
    await e.reply("PONG")