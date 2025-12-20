"""
Main bot module for anime-bot.

This module contains the Telegram bot client, event handlers, and the main
entry point for the application.
"""
import asyncio
import logging
from typing import Dict, Any, Optional

from telethon import TelegramClient, events, Button
from telethon.tl.custom.message import Message

from .config import settings
from .constants import (
    MAX_SEARCH_RESULTS,
    MAX_EPISODE_BUTTONS,
    MAX_TITLE_LENGTH,
    TITLE_TRUNCATE_LENGTH,
    EPISODES_PER_ROW,
    MAX_EPISODE_LIST_LENGTH,
    TRUNCATED_EPISODE_LIST_LENGTH,
    DEFAULT_QUALITY,
    DEFAULT_AUDIO,
)
from .logging_config import configure_logging
from .db import init_db, get_latest_uploaded, list_uploaded_for_anime
from .anime_api import AnimePaheClient
from .uploader import Uploader
from .tasks import DownloadUploadTask
from .utils import (
    validate_episode_spec,
    expand_episode_spec_to_list,
    pick_episodes_from_episode_list,
    load_from_cache,
    fuzzy_score,
)
from .cleanup import cleanup_loop
from .redis_client import RedisClient

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

# Ephemeral session store: chat_id -> dict with anime selection state
# Keys: anime_slug, anime_title, available_episodes
SESSION_STORE: Dict[int, Dict[str, Any]] = {}

client = TelegramClient("anime_bot", settings.tg_api_id, settings.tg_api_hash)
uploader = Uploader(client, concurrency=settings.max_upload_concurrency)
api = AnimePaheClient(verify_ssl=False)

stop_event = asyncio.Event()


async def on_startup() -> None:
    """Initialize the database and start the Telegram client."""
    await init_db()
    await client.start(bot_token=settings.tg_bot_token)
    logger.info("Bot started")


# @client.on(events.NewMessage(pattern=r"^/start$"))
# async def start_handler(event: events.NewMessage.Event) -> None:
#     """Handle the /start command."""
#     await event.reply(
#         "Hello — send `/search <anime name>` to search for anime. "
#         "After selecting an anime send an episode list like `1-3` or use `/download <slug> <spec>`."
#     )

@client.on(events.NewMessage(pattern=r"^/search\s+(.+)$"))
async def search_handler(event: events.NewMessage.Event) -> None:
    """Handle the /search command to find anime by name."""
    query = event.pattern_match.group(1).strip()
    msg = await event.reply(f"Searching for `{query}` ...")
    try:
        # results = await api.search(query)
        results = await load_from_cache(api)
    except Exception as exc:
        logger.exception("Search failed")
        await msg.edit(f"Search failed: {exc}")
        return

    if not results:
        await msg.edit(f"No results for `{query}`")
        return

    # build up to MAX_SEARCH_RESULTS result buttons
    # TODO; update to implement search logic

    # Score results quickly
    scored = []
    for result in results:
        title = result.get("title") or result.get("name") or ""
        score = fuzzy_score(title, query)
        if score > 0:
            scored.append((score, result))

    # Sort by score descending and keep only MAX_SEARCH_RESULTS
    # top_results = [r for _, r in sorted(scored, reverse=True)[:MAX_SEARCH_RESULTS]]
    scores_sorted = sorted(scored, key=lambda x: x[0], reverse=True)
    top_results = [result for _, result in scores_sorted[:MAX_SEARCH_RESULTS]]

    buttons = []
    for result in top_results:
        title = result.get("title") or result.get("name")
        session = result.get("session")
        label = title if len(title) < MAX_TITLE_LENGTH else title[:TITLE_TRUNCATE_LENGTH] + "..."
        payload = f"SELECT|{session}|{title}"
        payload = f"SELECT|{session}"
        buttons.append([Button.inline(label, payload.encode())])

    await msg.edit("Select an anime from results:", buttons=buttons)

@client.on(events.CallbackQuery(pattern=b"SELECT"))
async def select_callback(event: events.CallbackQuery.Event) -> None:
    """Handle anime selection callback from search results."""
    # format: SELECT|session|title
    data = event.data.decode()
    # _, session, title = data.split("|",2)
    _, session = data.split("|", 2)
    # chat_id = event._client._bot_token and event.sender_id or event.chat_id  # simpler to use event.chat_id
    chat_id = event.chat_id

    # Get anime title from session
    results = await load_from_cache(api)
    title = None
    for result in results:
        if session == result.get("session"):
            title = result.get("title")
            break

    notice = await event.edit(f"Selected **{title}** — fetching episode list ...")
    try:
        eps = await api.fetch_episodes(title, session)
    except Exception as exc:
        logger.exception("fetch_episodes failed")
        await notice.edit(f"Failed to fetch episodes: {exc}")
        return

    if not eps:
        await notice.edit("No episodes found.")
        return

    # store in session
    SESSION_STORE[chat_id] = {
        "anime_slug": session,
        "anime_title": title,
        "available_episodes": eps,
    }

    # present first MAX_EPISODE_BUTTONS episodes as buttons
    btns = []
    for ep in eps[:MAX_EPISODE_BUTTONS]:
        label = f"Ep {ep['episode']}"
        payload = f"PICK_EP|{ep['episode']}"
        btns.append(Button.inline(label, payload.encode()))

    # split into rows of EPISODES_PER_ROW
    rows = [btns[i : i + EPISODES_PER_ROW] for i in range(0, len(btns), EPISODES_PER_ROW)]
    # add helper buttons
    rows.append([Button.inline("List all episodes", b"LIST_ALL")])
    rows.append([Button.inline("I'll send ep spec", b"SEND_SPEC")])

    await notice.edit(
        f"Fetched {len(eps)} episodes for **{title}**. Tap episode buttons to quickly select "
        f"single ep, or press `I'll send ep spec` and then send something like `1-3,5`.\n"
        f"You can also use `/download {session} 1-3` directly.",
        buttons=rows,
    )

@client.on(events.CallbackQuery(pattern=b"PICK_EP"))
async def pick_episode_callback(event: events.CallbackQuery.Event) -> None:
    """Handle single episode selection callback."""
    # payload: PICK_EP|<num>
    data = event.data.decode()
    _, num = data.split("|", 1)
    chat_id = event.chat_id
    session_data = SESSION_STORE.get(chat_id)
    if not session_data:
        await event.answer("Session expired. Please /search again.", alert=True)
        return
    # find episode dict
    eps = session_data["available_episodes"]
    match = next((ep for ep in eps if str(ep["episode"]) == str(num)), None)
    if not match:
        await event.answer("Episode not found", alert=True)
        return

    # start task for single episode
    status_msg = await event.respond(f"Queued download for {session_data['anime_title']} ep {num} ...")
    task = DownloadUploadTask(
        client,
        session_data["anime_title"],
        session_data["anime_slug"],
        [match],
        chat_id,
        uploader,
        uploader_id=event.message.peer_id.user_id,
    )
    asyncio.create_task(task.run(status_callback=lambda t: status_msg.edit(t)))
    await event.answer("Queued", alert=False)

@client.on(events.CallbackQuery(pattern=b"LIST_ALL"))
async def list_all_callback(event: events.CallbackQuery.Event) -> None:
    """Handle callback to list all available episodes."""
    chat_id = event.chat_id
    session_data = SESSION_STORE.get(chat_id)
    if not session_data:
        await event.answer("Session expired. Please /search again.", alert=True)
        return
    lines = [f"Ep {ep['episode']}" for ep in session_data["available_episodes"]]
    txt = ", ".join(lines)
    if len(txt) > MAX_EPISODE_LIST_LENGTH:
        txt = txt[:TRUNCATED_EPISODE_LIST_LENGTH] + " ... (truncated) "
    await event.respond(f"All episodes:\n{txt}")


@client.on(events.CallbackQuery(pattern=b"SEND_SPEC"))
async def send_spec_callback(event: events.CallbackQuery.Event) -> None:
    """Handle callback when user wants to send episode specification manually."""
    chat_id = event.chat_id
    session_data = SESSION_STORE.get(chat_id)
    if not session_data:
        await event.answer("Session expired. Please /search again.", alert=True)
        return
    await event.respond(
        "OK — please reply in this chat with the episode spec (e.g. `1`, `1-3`, or `1,3,5-7`). "
        "Use `/download <slug> <spec>` if you prefer."
    )

@client.on(events.NewMessage(pattern=r"^/download\s+(\S+)\s+(.+)$"))
async def download_command(event: events.NewMessage.Event) -> None:
    """Handle the /download command to download specific episodes."""
    anime_slug = event.pattern_match.group(1).strip()
    spec = event.pattern_match.group(2).strip()
    if not validate_episode_spec(spec):
        await event.reply("Invalid episode spec format. Use examples like `1`, `1-3`, `1,3,5-7`.")
        return
    # We need anime title and episode sessions — try to find title via search by slug
    # Best-effort: search by slug (session) may not be title.
    # We attempt to get episodes by calling fetch_episodes with slug as name (api expects name+slug per docs).
    # Simplest approach: ask user to perform /search and then /download by replying with spec
    # — but still support direct /download if user knows slug.
    # We'll attempt to fetch episodes using slug as both name and slug; if that fails, ask user to /search then send spec.
    status_msg = await event.reply(f"Checking if entered episode[s] are valid for {anime_slug} episodes: {spec}")
    try:
        eps = await api.fetch_episodes(anime_slug, anime_slug)
    except Exception:
        eps = []
    if not eps:
        await event.reply(
            "Could not fetch episodes using the provided slug. "
            "Please use `/search <anime>` then select the anime and send episode spec, or give the correct slug."
        )
        return

    desired_nums = expand_episode_spec_to_list(spec)
    chosen = [ep for ep in eps if int(ep["episode"]) in desired_nums]
    if not chosen:
        await event.reply("No matching episodes found for the spec.")
        return

    # Try to fetch anime title using session [anime_slug]
    anime_title = anime_slug
    try:
        results = await load_from_cache(api)
        for result in results:
            if result.get("session", "") == anime_slug:
                if result.get("title", None):
                    anime_title = result.get("title")
                break
    except Exception:
        logger.exception("Loading from cache failed!")
        return

    await status_msg.edit(f"Queued download for {anime_slug} episodes {spec}")
    task = DownloadUploadTask(
        client,
        anime_title,
        anime_slug,
        chosen,
        event.chat_id,
        uploader,
        event.message.peer_id.user_id,
        quality=DEFAULT_QUALITY,
        audio=DEFAULT_AUDIO,
    )
    asyncio.create_task(task.run(status_callback=lambda t: status_msg.edit(t)))

@client.on(events.NewMessage(pattern=r"^(\d+(-\d+)?(,\d+(-\d+)?)*)$"))
async def spec_reply_handler(event: events.NewMessage.Event) -> None:
    """
    Handle episode specification sent as a plain message.

    If user sends just an episode spec and has a session stored in SESSION_STORE,
    interpret it as download request.
    """
    chat_id = event.chat_id
    session_data = SESSION_STORE.get(chat_id)
    if not session_data:
        # not in selection flow
        return
    spec = event.raw_text.strip()
    if not validate_episode_spec(spec):
        await event.reply("Invalid episode spec. Examples: `1`, `1-3`, `1,3,5-7`.")
        return
    eps = session_data["available_episodes"]
    desired = expand_episode_spec_to_list(spec)
    chosen = [ep for ep in eps if int(ep["episode"]) in desired]
    if not chosen:
        await event.reply("No matching episodes found in this anime for that spec.")
        return
    status_msg = await event.reply(f"Queued download for {session_data['anime_title']} episodes {spec}")
    # TODO fox
    task = DownloadUploadTask(
        client,
        session_data["anime_title"],
        session_data["anime_slug"],
        chosen,
        chat_id,
        uploader,
        uploader_id=event.sender_id,
    )
    asyncio.create_task(task.run(status_callback=lambda t: status_msg.edit(t)))

@client.on(events.NewMessage(pattern=r"^/get\s+(.+?)\s+(\d+)$"))
async def get_command(event: events.NewMessage.Event) -> None:
    """Handle the /get command to retrieve a cached episode."""
    anime = event.pattern_match.group(1).strip()
    ep = int(event.pattern_match.group(2))
    row = await get_latest_uploaded(anime, ep)
    if not row:
        await event.reply(f"No cached file for {anime} ep {ep}. Use /search and download.")
        return
    try:
        # Prefer sending as a copy so the forwarded file appears as a new message
        # (no "forwarded from" header). Telethon supports `as_copy=True`.
        await client.forward_messages(
            event.chat_id,
            message_ids=row.uploaded_message_id,
            from_peer=row.uploaded_chat_id,
            as_copy=True,
        )
        await event.reply("Sent from cache.")
    except Exception as exc:
        # Fallback: fetch the original message and re-upload its media using send_file.
        logger.exception("forward as copy failed, attempting fallback send_file")
        try:
            # get_messages will return the original message object
            orig = await client.get_messages(row.uploaded_chat_id, ids=row.uploaded_message_id)
            if orig and orig.media:
                await client.send_file(event.chat_id, orig.media)#, caption=orig.caption)
                await event.reply("Sent from cache (re-uploaded).")
            else:
                await event.reply("Cached record has no media to send.")
        except Exception as exc2:
            logger.exception("fallback send_file failed")
            await event.reply(f"Could not send cached file: {exc2}")

# @client.on(events.NewMessage(pattern=r"^/list\s+(.+)$"))
# async def list_cmd(event: events.NewMessage.Event):
#     anime = event.pattern_match.group(1).strip()
#     rows = await list_uploaded_for_anime(anime)
#     if not rows:
#         await event.reply("No cached uploads found")
#         return
#     lines = [f"Ep {r.episode} — {r.filename} ({r.created_at})" for r in rows]
#     msg = "\n".join(lines)
#     if len(msg) > 4000:
#         msg = msg[:3800] + "\n...truncated..."
#     await event.reply(msg)

async def main() -> None:
    """Main entry point for the bot application."""
    await on_startup()
    loop = asyncio.get_event_loop()
    cleanup_task = loop.create_task(cleanup_loop(stop_event))
    try:
        await client.run_until_disconnected()
    finally:
        stop_event.set()
        await cleanup_task
        await RedisClient.close()

# if __name__ == "__main__":
#     asyncio.run(main())
