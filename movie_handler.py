"""Search and format results from the Movie Downloader API."""

import asyncio
import html
import logging
import re
import secrets
import time
from typing import Dict, List, Optional
from urllib.parse import urlsplit

import aiohttp
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)
_MOVIE_SESSIONS = {}
_MOVIE_SESSION_TTL = 2 * 60 * 60
_MAX_SELECTIONS_PER_SEARCH = 1000


class MovieAPI:
    """Small async client for the public Movie Downloader search endpoint."""

    BASE_URL = "https://movie-downloader-api.vercel.app/api"
    TIMEOUT_SECONDS = 15

    @staticmethod
    async def search(query: str) -> Optional[List[Dict]]:
        """Return search results, an empty list for no matches, or None on API errors."""
        query = (query or "").strip()
        if not query:
            return []

        try:
            timeout = aiohttp.ClientTimeout(total=MovieAPI.TIMEOUT_SECONDS)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{MovieAPI.BASE_URL}/search",
                    params={"q": query},
                    headers={"Accept": "application/json"},
                ) as response:
                    if response.status != 200:
                        logger.warning("Movie API returned HTTP %s", response.status)
                        return None
                    payload = await response.json(content_type=None)

            results = payload.get("results") if isinstance(payload, dict) else payload
            if not isinstance(results, list):
                logger.warning("Movie API response did not contain a results list")
                return None
            return [item for item in results if isinstance(item, dict)]
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            logger.exception("Movie API request failed")
            return None
        except Exception:
            logger.exception("Unexpected error while querying Movie API")
            return None


def format_movie_results(results: List[Dict], limit: int = 5) -> str:
    """Render API results as Telegram-safe HTML, including available metadata."""
    blocks = ["🎬 <b>Movie Search Results</b>"]

    for index, item in enumerate(results[:limit], 1):
        title = html.escape(str(item.get("title") or "Untitled")[:120])
        year = item.get("year")
        kind = html.escape(str(item.get("type") or "Title")[:40])
        line = f"<b>{index}. {title}</b>"
        if year:
            line += f" ({html.escape(str(year)[:12])})"
        line += f" · {kind}"

        details = []
        rating = item.get("rating")
        if rating not in (None, "", "N/A"):
            details.append(f"⭐ {html.escape(str(rating)[:12])}/10")
        country = item.get("country")
        if country:
            details.append(f"🌐 {html.escape(str(country)[:50])}")

        episodes = item.get("episodes")
        episodes = episodes if isinstance(episodes, list) else []
        raw_languages = item.get("languages")
        if isinstance(raw_languages, list):
            languages = [
                (
                    language.get("language") or language.get("name")
                    if isinstance(language, dict)
                    else language
                )
                for language in raw_languages
            ]
        else:
            languages = []
        if not languages:
            languages = [
                episode.get("language")
                for episode in episodes
                if isinstance(episode, dict) and episode.get("language")
            ]
        languages = list(
            dict.fromkeys(str(language) for language in languages if language)
        )
        language_text = ", ".join(str(language) for language in languages[:8])
        if language_text:
            details.append(f"🔊 {html.escape(language_text[:120])}")
        if episodes:
            seasons = item.get("seasons")
            season_count = len(seasons) if isinstance(seasons, list) else 0
            episode_numbers = {
                (episode.get("season"), episode.get("episode"))
                for episode in episodes
                if isinstance(episode, dict) and episode.get("episode") is not None
            }
            episode_count = len(episode_numbers) or len(episodes)
            episode_text = f"📺 {episode_count} episodes"
            if season_count:
                episode_text += f" · {season_count} season(s)"
            details.append(episode_text)

        blocks.append(line)
        if details:
            blocks.append("\n".join(details))

    return "\n\n".join(blocks)


def _quality_score(quality: Dict) -> int:
    match = re.search(r"(\d+)", str(quality.get("quality") or ""))
    return int(match.group(1)) if match else 0


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _language_name(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("language") or value.get("name")
    return str(value or "Unknown")[:40]


def create_movie_session(results: List[Dict], chat_id: int) -> Optional[str]:
    """Store safe callback selections for one search result message."""
    selections = []
    for item in results[:5]:
        title = str(item.get("title") or "Untitled")[:120]
        item_languages = item.get("languages")
        fallback_language = (
            _language_name(item_languages[0])
            if isinstance(item_languages, list) and len(item_languages) == 1
            else "Unknown"
        )
        episodes = item.get("episodes")
        if not isinstance(episodes, list):
            continue
        for episode in episodes:
            if not isinstance(episode, dict):
                continue
            language = _language_name(episode.get("language") or fallback_language)
            qualities = episode.get("qualities")
            if not isinstance(qualities, list):
                continue
            for quality in qualities:
                if not isinstance(quality, dict):
                    continue
                url = quality.get("download_url") or quality.get("downloadUrl")
                if not _is_http_url(url):
                    continue
                selections.append(
                    {
                        "title": title,
                        "season": episode.get("season"),
                        "episode": episode.get("episode"),
                        "language": language,
                        "quality": str(quality.get("quality") or "Available")[:20],
                        "url": url,
                        "duration": episode.get("duration") or item.get("duration"),
                        "thumbnail": item.get("poster") or item.get("thumbnail"),
                    }
                )
                if len(selections) >= _MAX_SELECTIONS_PER_SEARCH:
                    break
            if len(selections) >= _MAX_SELECTIONS_PER_SEARCH:
                break
        if len(selections) >= _MAX_SELECTIONS_PER_SEARCH:
            break

    if not selections:
        return None
    now = time.time()
    for session_id, session in list(_MOVIE_SESSIONS.items()):
        if now - session["created_at"] > _MOVIE_SESSION_TTL:
            _MOVIE_SESSIONS.pop(session_id, None)
    while len(_MOVIE_SESSIONS) >= 500:
        oldest = min(
            _MOVIE_SESSIONS, key=lambda key: _MOVIE_SESSIONS[key]["created_at"]
        )
        _MOVIE_SESSIONS.pop(oldest, None)

    session_id = secrets.token_hex(5)
    _MOVIE_SESSIONS[session_id] = {
        "chat_id": chat_id,
        "created_at": now,
        "page": 0,
        "language": None,
        "quality": None,
        "selections": selections,
    }
    return session_id


def get_movie_session(session_id: str, chat_id: Optional[int] = None) -> Optional[Dict]:
    session = _MOVIE_SESSIONS.get(session_id)
    if not session:
        return None
    if time.time() - session["created_at"] > _MOVIE_SESSION_TTL:
        _MOVIE_SESSIONS.pop(session_id, None)
        return None
    if chat_id is not None and session["chat_id"] != chat_id:
        return None
    return session


def get_movie_selection(
    session_id: str, index: int, chat_id: Optional[int] = None
) -> Optional[Dict]:
    session = get_movie_session(session_id, chat_id)
    if not session or index < 0 or index >= len(session["selections"]):
        return None
    return session["selections"][index]


def set_movie_page(session_id: str, page: int) -> Optional[Dict]:
    session = get_movie_session(session_id)
    if not session:
        return None
    session["page"] = max(0, page)
    return session


def cycle_movie_filter(session_id: str, field: str) -> Optional[Dict]:
    session = get_movie_session(session_id)
    if not session or field not in {"language", "quality"}:
        return None
    choices = sorted(
        {selection[field] for selection in session["selections"] if selection[field]},
        key=str.casefold,
    )
    options = [None, *choices]
    current = session[field]
    try:
        next_index = (options.index(current) + 1) % len(options)
    except ValueError:
        next_index = 0
    session[field] = options[next_index]
    session["page"] = 0
    return session


def reset_movie_filters(session_id: str) -> Optional[Dict]:
    session = get_movie_session(session_id)
    if not session:
        return None
    session["language"] = None
    session["quality"] = None
    session["page"] = 0
    return session


def create_movie_keyboard(
    session_id: str, max_buttons: int = 8
) -> Optional[InlineKeyboardMarkup]:
    """Build a paginated callback keyboard without removing other episode choices."""
    session = get_movie_session(session_id)
    if not session:
        return None
    selections = session["selections"]
    filtered = [
        index
        for index, selection in enumerate(selections)
        if (session["language"] is None or selection["language"] == session["language"])
        and (session["quality"] is None or selection["quality"] == session["quality"])
    ]
    page_count = max(1, (len(filtered) + max_buttons - 1) // max_buttons)
    page = min(session["page"], page_count - 1)
    session["page"] = page
    rows = []

    if filtered:
        start = page * max_buttons
        for index in filtered[start : start + max_buttons]:
            selection = selections[index]
            label = selection["title"][:12]
            season = selection.get("season")
            episode = selection.get("episode")
            if season is not None and episode is not None:
                label += f" S{season}E{episode}"
            label += f" {selection['language'][:10]} {selection['quality'][:8]}"
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"▶ {label}"[:60],
                        callback_data=f"movie:select:{session_id}:{index}",
                    )
                ]
            )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="No matches — reset filters",
                    callback_data=f"movie:reset:{session_id}",
                )
            ]
        )

    if page_count > 1:
        navigation = []
        if page > 0:
            navigation.append(
                InlineKeyboardButton(
                    text="⬅️ Previous",
                    callback_data=f"movie:page:{session_id}:{page - 1}",
                )
            )
        if page + 1 < page_count:
            navigation.append(
                InlineKeyboardButton(
                    text="Next ➡️",
                    callback_data=f"movie:page:{session_id}:{page + 1}",
                )
            )
        rows.append(navigation)

    language = session["language"] or "All"
    quality = session["quality"] or "All"
    rows.append(
        [
            InlineKeyboardButton(
                text=f"🌐 Language: {language[:16]}",
                callback_data=f"movie:language:{session_id}",
            ),
            InlineKeyboardButton(
                text=f"🎞 Quality: {quality[:12]}",
                callback_data=f"movie:quality:{session_id}",
            ),
        ]
    )
    return InlineKeyboardMarkup(rows)
