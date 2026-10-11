"""Search and format results from the Movie Downloader API."""

import asyncio
import html
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlsplit

import aiohttp
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


logger = logging.getLogger(__name__)


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
                language.get("language") or language.get("name")
                if isinstance(language, dict)
                else language
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
        languages = list(dict.fromkeys(str(language) for language in languages if language))
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
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def create_movie_keyboard(
    results: List[Dict], max_buttons: int = 8
) -> Optional[InlineKeyboardMarkup]:
    """Create links for the best quality of the first episode per available language."""
    rows = []

    for item in results:
        title = str(item.get("title") or "Title")
        episodes = item.get("episodes")
        if not isinstance(episodes, list):
            continue

        # Keep one button per language (first available episode), rather than
        # generating an unmanageably large keyboard for a whole season.
        seen_languages = set()
        for episode in episodes:
            if not isinstance(episode, dict):
                continue
            language = str(episode.get("language") or "")
            language_key = language.casefold()
            if language_key in seen_languages:
                continue

            qualities = episode.get("qualities")
            if not isinstance(qualities, list):
                continue
            usable = [
                quality for quality in qualities
                if isinstance(quality, dict)
                and _is_http_url(quality.get("download_url") or quality.get("downloadUrl"))
            ]
            if not usable:
                continue

            quality = max(usable, key=_quality_score)
            url = quality.get("download_url") or quality.get("downloadUrl")
            season = episode.get("season")
            episode_number = episode.get("episode")
            resolution = str(quality.get("quality") or "Available")
            label = f"▶ {title[:16]}"
            if season and episode_number:
                label += f" S{season}E{episode_number}"
            if language:
                label += f" {language[:10]}"
            label += f" {resolution[:8]}"
            rows.append([InlineKeyboardButton(text=label[:60], url=url)])
            seen_languages.add(language_key)

            if len(rows) >= max_buttons:
                return InlineKeyboardMarkup(rows)

    return InlineKeyboardMarkup(rows) if rows else None
