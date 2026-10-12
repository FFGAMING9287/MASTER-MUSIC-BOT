"""
Movie API helper for MusicPlayer
Integrates https://movie-downloader-api.vercel.app
"""

import aiohttp
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MOVIE_API = "https://movie-downloader-api.vercel.app/api/search"

async def search_movie(query: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MOVIE_API}?q={query}", timeout=15) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("results", [])
    except Exception as e:
        print(f"Movie search error: {e}")
        return None

def build_movie_buttons(results):
    if not results:
        return None
    result = results[0]
    title = result.get("title", "Unknown")
    buttons = []
    episodes = result.get("episodes", [])[:12]  # limit
    for ep in episodes:
        season = ep.get("season", 1)
        episode = ep.get("episode", 1)
        lang = ep.get("language", "Japanese")
        for q in ep.get("qualities", [])[:2]:
            quality = q.get("quality", "480p")
            url = q.get("download_url") or q.get("downloadUrl") or ""
            label = f"▶️ {title} S{season}E{episode} {lang} {quality}"
            # callback limited to 64 bytes
            cb = f"mv|{season}|{episode}|{lang[:8]}|{quality}|{url[-40:]}"
            buttons.append([InlineKeyboardButton(label[:58], callback_data=cb[:64])])
    if len(buttons) > 0:
        buttons.append([InlineKeyboardButton("🌐 Language: All", callback_data="mv_lang"), InlineKeyboardButton("📺 Quality: All", callback_data="mv_qual")])
    return InlineKeyboardMarkup(buttons) if buttons else None
