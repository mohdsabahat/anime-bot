from collections import defaultdict
from telethon import Button, events
import urllib

from ..utils import fuzzy_score
from ..bot import client
from ..db import list_uploaded_for_anime, list_distinct_anime_titles



@client.on(events.NewMessage(pattern=r"^/list\s+(.+)$"))
async def list_cmd(event: events.NewMessage.Event):
    """
    Enhanced /list:
      - tries exact match first
      - if not found, fuzzy-search over distinct titles stored in DB
      - present grouped summary (title, total episodes, per-language counts)
      - provide inline button to view full uploads for a chosen title
    """
    query = event.pattern_match.group(1).strip()
    # try exact first
    rows = await list_uploaded_for_anime(query, limit=200)
    if rows:
        # exact match found — show detailed list directly
        lines = [f"Ep {r.episode} — {r.filename} ({r.created_at:%Y-%m-%d %H:%M})" for r in rows]
        msg = "\n".join(lines)
        if len(msg) > 4000:
            msg = msg[:3800] + "\n...truncated..."
        await event.reply(f"Uploads for exact title: {query}\n\n{msg}")
        return

    titles = await list_distinct_anime_titles()
    scored = []
    for t in titles:
        score = fuzzy_score(t, query)
        if score > 0:
            scored.append((score, t))
    if not scored:
        await event.reply(f"No cached uploads matching `{query}` (no fuzzy candidates). Try a different query.")
        return

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [t for _, t in scored[:10]]  # limit results

    # For each candidate title compute counts and per-language breakdown
    buttons = []
    summary_lines = []
    for title in top:
        rows = await list_uploaded_for_anime(title, limit=1000)
        # compute unique episodes per language (prefer counting episodes)
        lang_to_eps = defaultdict(set)
        # for r in rows:
        #     lang = _guess_language_from_filename(r.filename)
        #     lang_to_eps[lang].add(r.episode)
        lang_counts = {lang: len(eps) for lang, eps in lang_to_eps.items()}
        total_eps = sum(lang_counts.values())
        # build language summary string
        lang_parts = [f"{lang.upper()}: {cnt}" for lang, cnt in sorted(lang_counts.items(), key=lambda x: -x[1])]
        lang_str = ", ".join(lang_parts) if lang_parts else "unknown"
        summary_lines.append(f"{title} — {total_eps} uploaded — langs: {lang_str}")
        # button payload: encode title safely
        payload = "LIST_BY_TITLE|" + urllib.parse.quote_plus(title)
        buttons.append([Button.inline("View uploads", payload.encode())])
    msg = "Search results:\n\n" + "\n".join(summary_lines)
    if len(msg) > 4000:
        msg = msg[:3900] + "\n...truncated..."
    await event.reply(msg, buttons=buttons)

@client.on(events.CallbackQuery(pattern=b"LIST_BY_TITLE"))
async def list_by_title_cb(event: events.CallbackQuery.Event):
    """
    Callback when user presses 'View uploads' for a fuzzy search result.
    Payload: LIST_BY_TITLE|<quote_plus(title)>
    """
    data = event.data.decode()
    try:
        _, enc = data.split("|", 1)
    except ValueError:
        await event.answer("Invalid payload", alert=True)
        return
    title = urllib.parse.unquote_plus(enc)
    rows = await list_uploaded_for_anime(title, limit=500)
    if not rows:
        await event.edit(f"No cached uploads found for {title}.")
        return

    lines = [f"Ep {r.episode} — {r.filename} ({r.created_at:%Y-%m-%d %H:%M})" for r in rows]
    txt = "\n".join(lines)
    if len(txt) > 4000:
        txt = txt[:3800] + "\n...truncated..."
    # edit the message that contained the button (or send a new reply if editing is not appropriate)
    try:
        await event.edit(f"Uploads for {title}:\n\n{txt}")
    except Exception:
        await event.respond(f"Uploads for {title}:\n\n{txt}")