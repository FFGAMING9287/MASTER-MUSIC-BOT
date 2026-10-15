"""
YouTube download with yt-dlp
android_vr first (no JS needed), then web clients with cookies
"""

import asyncio
import os
from yt_dlp import YoutubeDL

# android_vr bypasses broken JS n-challenge on cloud servers
# web/mweb need cookies; ios ignores cookies
CLIENT_STRATEGIES = [
    # (client, use_cookies)
    ("android_vr", False),
    ("android_vr", True),
    ("android", False),
    ("android", True),
    ("web_embedded", True),
    ("mweb", True),
    ("tv", True),
    ("web", True),
]

BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "noplaylist": True,
    "source_address": "0.0.0.0",
    "force_ipv4": True,
}

DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def _find_cookies():
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


def _base_opts(use_cookies=True):
    opts = dict(BASE_OPTS)
    if use_cookies:
        cookies = _find_cookies()
        if cookies:
            opts["cookiefile"] = cookies
    return opts


def _search_sync(query: str, limit: int = 5):
    opts = _base_opts(True)
    opts["extract_flat"] = "in_playlist"
    opts["default_search"] = "ytsearch"
    results = []
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            if not info:
                return []
            for e in (info.get("entries") or []):
                if not e:
                    continue
                vid = e.get("id") or ""
                results.append({
                    "id": vid,
                    "title": e.get("title") or "Unknown",
                    "duration": e.get("duration") or 0,
                    "uploader": e.get("uploader") or e.get("channel") or "",
                    "url": e.get("url") or e.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}",
                    "thumb": e.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                })
    except Exception as e:
        print(f"YT search error: {e}")
    return results


def _find_downloaded(vid: str, info: dict):
    candidates = []
    if info.get("_filename") and os.path.isfile(info["_filename"]):
        candidates.append(info["_filename"])
    for rd in (info.get("requested_downloads") or []):
        fp = rd.get("filepath")
        if fp and os.path.isfile(fp):
            candidates.append(fp)
    for ext in ("m4a", "webm", "mp4", "mp3", "opus", "mkv", "wav"):
        p = os.path.join(DOWNLOADS_DIR, f"{vid}.{ext}")
        if os.path.isfile(p):
            candidates.append(p)
    try:
        for name in os.listdir(DOWNLOADS_DIR):
            if name.startswith(vid) and os.path.isfile(os.path.join(DOWNLOADS_DIR, name)):
                candidates.append(os.path.join(DOWNLOADS_DIR, name))
    except Exception:
        pass
    for c in candidates:
        if os.path.isfile(c) and os.path.getsize(c) > 1000:
            return c
    return None


def _download_sync(url: str):
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
        url = f"https://www.youtube.com/watch?v={vid}"

    outtmpl = os.path.join(DOWNLOADS_DIR, "%(id)s.%(ext)s")

    for client, use_cookies in CLIENT_STRATEGIES:
        opts = _base_opts(use_cookies)
        opts["outtmpl"] = outtmpl
        opts["extractor_args"] = {
            "youtube": {
                "player_client": [client],
                "player_skip": ["webpage", "configs"],
            }
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    continue
                vid = info.get("id") or ""
                path = _find_downloaded(vid, info)
                if path:
                    print(f"YT OK client={client} cookies={use_cookies} path={path}")
                    return {
                        "path": path,
                        "title": info.get("title") or "YouTube",
                        "duration": info.get("duration") or 0,
                        "uploader": info.get("uploader") or "",
                        "webpage": info.get("webpage_url") or url,
                    }
                print(f"YT client={client}: no file after download")
        except Exception as e:
            print(f"YT client={client} cookies={use_cookies}: {e}")
            continue

    return None


def _get_stream_url_sync(url: str):
    result = _download_sync(url)
    if not result:
        return None
    return {
        "url": result["path"],
        "path": result["path"],
        "title": result["title"],
        "duration": result["duration"],
        "uploader": result["uploader"],
        "thumb": "",
        "webpage": result["webpage"],
        "is_local": True,
    }


async def search_youtube(query: str, limit: int = 5):
    return await asyncio.to_thread(_search_sync, query, limit)


async def get_stream_info(url: str):
    return await asyncio.to_thread(_get_stream_url_sync, url)
