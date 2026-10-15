"""
YouTube search + stream URL extraction with yt-dlp
Tries cookies + multiple player clients to bypass bot detection.
"""

import asyncio
import os
from yt_dlp import YoutubeDL

PLAYER_CLIENTS = [
    "android",
    "ios",
    "tv",
    "mweb",
    "web",
]

BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "noplaylist": True,
    "source_address": "0.0.0.0",
}


def _find_cookies():
    """Find cookies.txt in common locations."""
    candidates = [
        os.path.join(os.getcwd(), "cookies.txt"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cookies.txt"),
        "/MusicPlayer/cookies.txt",
        "/app/cookies.txt",
        "cookies.txt",
    ]
    for p in candidates:
        if os.path.isfile(p):
            print(f"Using cookies: {p}")
            return p
    print("No cookies.txt found")
    return None


def _base_opts():
    opts = dict(BASE_OPTS)
    cookies = _find_cookies()
    if cookies:
        opts["cookiefile"] = cookies
    return opts


def _search_sync(query: str, limit: int = 5):
    opts = _base_opts()
    opts["extract_flat"] = "in_playlist"
    opts["default_search"] = "ytsearch"
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


def _extract_with_client(url: str, client: str):
    opts = _base_opts()
    opts["format"] = "bestaudio[ext=m4a]/bestaudio/best"
    opts["extractor_args"] = {"youtube": {"player_client": [client]}}
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None
            stream_url = info.get("url")
            if not stream_url and info.get("formats"):
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
        print(f"YT client={client} error: {e}")
        return None


def _get_stream_url_sync(url: str):
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
        url = f"https://www.youtube.com/watch?v={vid}"

    for client in PLAYER_CLIENTS:
        result = _extract_with_client(url, client)
        if result:
            print(f"YT stream OK with client={client}")
            return result

    opts = _base_opts()
    opts["format"] = "bestaudio/best"
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info:
                stream_url = info.get("url")
                if not stream_url and info.get("formats"):
                    for f in reversed(info["formats"]):
                        if f.get("url") and (f.get("acodec") or "none") != "none":
                            stream_url = f["url"]
                            break
                if stream_url:
                    return {
                        "url": stream_url,
                        "title": info.get("title") or "YouTube",
                        "duration": info.get("duration") or 0,
                        "uploader": info.get("uploader") or "",
                        "thumb": info.get("thumbnail") or "",
                        "webpage": info.get("webpage_url") or url,
                    }
    except Exception as e:
        print(f"YT final error: {e}")

    return None


async def search_youtube(query: str, limit: int = 5):
    return await asyncio.to_thread(_search_sync, query, limit)


async def get_stream_info(url: str):
    return await asyncio.to_thread(_get_stream_url_sync, url)
