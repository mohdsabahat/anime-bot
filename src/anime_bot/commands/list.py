"""
List command handler for anime-bot.

Provides functionality to list uploaded anime episodes with fuzzy search
and per-language breakdown.
"""
import urllib
from collections import defaultdict
from typing import List

from telethon import Button, events

from ..bot import client
from ..db import list_uploaded_for_anime, list_distinct_anime_titles, get_uploaded_file_by_id
from ..models import UploadedFile
from ..utils import fuzzy_score
from ..constants import MAX_MESSAGE_LENGTH, TRUNCATED_MESSAGE_LENGTH
from ..logging_config import configure_logging
import logging

# UI Constants for list command
MAX_TITLE_BUTTON_LENGTH = 20
MAX_SEARCH_RESULTS = 8

logger = logging.getLogger(__name__)

def format_file_size(size_bytes: int | None) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes, or None.

    Returns:
        Formatted string like "1.5 GB" or "N/A".
    """
    if size_bytes is None:
        return "N/A"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def truncate_title(title: str, max_length: int = MAX_TITLE_BUTTON_LENGTH) -> str:
    """Truncate title for button display.

    Args:
        title: The full title.
        max_length: Maximum length for display.

    Returns:
        Truncated title with ellipsis if needed.
    """
    if len(title) <= max_length -3 :
        return title
    return title[: max_length - 6] + "…"


def build_episode_summary(rows: List[UploadedFile]) -> dict:
    """Build a summary of episodes from database rows.

    Args:
        rows: List of UploadedFile records.

    Returns:
        Dictionary with episode counts, language breakdown, and quality info.
    """
    episodes = set()
    lang_counts = defaultdict(int)
    quality_counts = defaultdict(int)
    total_size = 0

    for row in rows:
        episodes.add(row.episode)
        if row.ep_lang:
            lang_counts[row.ep_lang.upper()] += 1
        if row.ep_qual:
            quality_counts[f"{row.ep_qual}p"] += 1
        if row.filesize:
            total_size += row.filesize

    return {
        "total_episodes": len(episodes),
        "episode_range": f"{min(episodes)}-{max(episodes)}" if episodes else "N/A",
        "languages": dict(lang_counts),
        "qualities": dict(quality_counts),
        "total_size": total_size,
        "file_count": len(rows),
    }


def format_episode_line(row: UploadedFile, index: int) -> str:
    """Format a single episode line for display.

    Args:
        row: The UploadedFile record.
        index: Line index for alternating formatting.

    Returns:
        Formatted string for the episode.
    """
    lang = row.ep_lang.upper() if row.ep_lang else "?"
    qual = f"{row.ep_qual}p" if row.ep_qual else "?"
    size = format_file_size(row.filesize)
    date = row.created_at.strftime("%Y-%m-%d") if row.created_at else "?"

    return f"📺 Ep {row.episode:02d} │ {lang} │ {qual} │ {size} │ {date}"


@client.on(events.NewMessage(pattern=r"^/list\s+(.+)$"))
async def list_command(event: events.NewMessage.Event) -> None:
    """Handle the /list command to show uploaded episodes.

    Enhanced /list:
      - Tries exact match first
      - If not found, fuzzy-search over distinct titles stored in DB
      - Present grouped summary (title, total episodes, per-language counts)
      - Provide inline button to view full uploads for a chosen title
    """
    query = event.pattern_match.group(1).strip()

    # Try exact match first
    rows = await list_uploaded_for_anime(query, limit=200)
    if rows:
        # Exact match found — show detailed list directly
        await _send_episode_list(event, query, rows, is_callback=False)
        return

    # Fuzzy search over distinct titles
    titles = await list_distinct_anime_titles()
    scored = []
    for title in titles:
        score = fuzzy_score(title, query)
        if score > 0:
            scored.append((score, title))

    if not scored:
        await event.reply(
            f"❌ No cached uploads matching `{query}`.\n\n"
            "💡 Try a different search term or check spelling."
        )
        return

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [title for _, title in scored[:MAX_SEARCH_RESULTS]]

    # Build summary and buttons for each result
    buttons = []
    summary_lines = ["🔍 **Search Results**\n"]

    for idx, title in enumerate(top, 1):
        rows = await list_uploaded_for_anime(title, limit=1000)
        summary = build_episode_summary(rows)

        # Format language info
        if summary["languages"]:
            lang_parts = [f"{lang}: {cnt}" for lang, cnt in summary["languages"].items()]
            lang_str = " | ".join(lang_parts)
        else:
            lang_str = "Unknown"

        # Format quality info
        if summary["qualities"]:
            qual_parts = [f"{qual}" for qual in sorted(summary["qualities"].keys())]
            qual_str = ", ".join(qual_parts)
        else:
            qual_str = "?"

        # Add numbered result line
        summary_lines.append(
            f"**{idx}.** {title}\n"
            f"    📊 {summary['total_episodes']} eps (Ep {summary['episode_range']})\n"
            f"    🌐 {lang_str} │ 🎬 {qual_str}\n"
        )

        # Create button with truncated title and include a representative id
        button_label = f"📋 {truncate_title(title)}"
        rep_id = rows[0].id if rows else None
        if rep_id is None:
            payload = f"LIST_BY_TITLE|{urllib.parse.quote_plus(title)}"
        else:
            payload = f"LIST_BY_ID|{rep_id}"
        buttons.append([Button.inline(button_label, payload.encode())])

    msg = "\n".join(summary_lines)
    if len(msg) > MAX_MESSAGE_LENGTH:
        msg = msg[: TRUNCATED_MESSAGE_LENGTH] + "\n\n...truncated..."

    await event.reply(msg, buttons=buttons, parse_mode="md")


async def _send_episode_list(
    event, title: str, rows: List[UploadedFile], is_callback: bool = False
) -> None:
    """Send formatted episode list to user.

    Args:
        event: The Telegram event.
        title: Anime title.
        rows: List of UploadedFile records.
        is_callback: Whether this is from a callback (edit) or new message (reply).
    """
    summary = build_episode_summary(rows)

    # Build header
    header_lines = [
        f"📺 **{title}**\n",
        f"📊 **{summary['total_episodes']} episodes** (Ep {summary['episode_range']})",
        f"💾 Total size: {format_file_size(summary['total_size'])}",
        f"📁 {summary['file_count']} files cached\n",
        "─" * 30,
    ]

    # Build episode list
    episode_lines = []
    for idx, row in enumerate(rows):
        episode_lines.append(format_episode_line(row, idx))

    full_msg = "\n".join(header_lines) + "\n" + "\n".join(episode_lines)

    if len(full_msg) > MAX_MESSAGE_LENGTH:
        # Truncate episode list but keep header
        header = "\n".join(header_lines)
        remaining = MAX_MESSAGE_LENGTH - len(header) - 50
        episode_text = "\n".join(episode_lines)
        if len(episode_text) > remaining:
            episode_text = episode_text[:remaining] + "\n\n⚠️ ...list truncated..."
        full_msg = header + "\n" + episode_text

    if is_callback:
        try:
            await event.edit(full_msg, parse_mode="md")
        except Exception:
            await event.respond(full_msg, parse_mode="md")
    else:
        await event.reply(full_msg, parse_mode="md")


@client.on(events.CallbackQuery(pattern=b"LIST_BY_ID"))
async def list_by_id_callback(event: events.CallbackQuery.Event) -> None:
    """Handle callback when user presses a fuzzy-search result button.

    Payload format: LIST_BY_ID|<uploaded_file_id>
    """
    data = event.data.decode()
    try:
        _, enc = data.split("|", 1)
    except ValueError:
        await event.answer("Invalid payload", alert=True)
        return

    try:
        file_id = int(enc)
    except ValueError:
        await event.answer("Invalid id", alert=True)
        return

    rep = await get_uploaded_file_by_id(file_id)
    if not rep:
        await event.answer("Could not find the selected record.", alert=True)
        return

    title = rep.anime_title
    rows = await list_uploaded_for_anime(title, limit=500)

    if not rows:
        await event.answer(f"No cached uploads found for {title}.", alert=True)
        return

    await event.answer("Loading episodes...")
    await _send_episode_list(event, title, rows, is_callback=True)