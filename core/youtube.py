"""
YouTube search + stream URL extraction with yt-dlp
"""

import asyncio
import os
from yt_dlp import YoutubeDL

# Better options for reliability in 2026
YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "extract_flat": False,
    "default_search": "ytsearch",
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": True,
    "source_address": "0.0.0.0",
}

# For getting streamable URL without full download
STREAM_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "format": "bestaudio[ext=m4a]/bestaudio/best",
    "noplaylist": True,
}


def _search_sync(query: str, limit: int = 5):
    opts = dict(YDL_OPTS)
    opts["extract_flat"] = "in_playlist"
    results = []
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            if not info:
                return []
            entries = info.get("entries") or []
            for e in entries:
                if not e:
                    continue
                vid = e.get("id") or ""
                title = e.get("title") or "Unknown"
                duration = e.get("duration") or 0
                uploader = e.get("uploader") or e.get("channel") or ""
                url = e.get("url") or e.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}"
                results.append({
                    "id": vid,
                    "title": title,
                    "duration": duration,
                    "uploader": uploader,
                    "url": url,
                    "thumb": e.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                })
    except Exception as e:
        print(f"YT search error: {e}")
    return results


def _get_stream_url_sync(url: str):
    """Extract direct stream URL + metadata."""
    try:
        with YoutubeDL(STREAM_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None
            # Prefer direct URL
            stream_url = info.get("url")
            if not stream_url and info.get("formats"):
                # Pick best audio format with a url
                for f in reversed(info["formats"]):
                    if f.get("url") and (f.get("acodec") or "none") != "none":
                        stream_url = f["url"]
                        break
            if not stream_url:
                return None
            return {
                "url": stream_url,
                "title": info.get("title") or "YouTube",
                "duration": info.get("duration") or 0,
                "uploader": info.get("uploader") or "",
                "thumb": info.get("thumbnail") or "",
                "webpage": info.get("webpage_url") or url,
            }
    except Exception as e:
        print(f"YT stream error: {e}")
        return None


async def search_youtube(query: str, limit: int = 5):
    return await asyncio.to_thread(_search_sync, query, limit)


async def get_stream_info(url: str):
    return await asyncio.to_thread(_get_stream_url_sync, url)
