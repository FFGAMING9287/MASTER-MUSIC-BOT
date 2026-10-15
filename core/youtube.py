"""
YouTube search + download with yt-dlp
Downloads audio to disk (more reliable than stream URL in 2026)
"""

import asyncio
import os
import tempfile
from yt_dlp import YoutubeDL

PLAYER_CLIENTS = ["android", "ios", "tv", "mweb", "web"]

BASE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "noplaylist": True,
    "source_address": "0.0.0.0",
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


def _download_sync(url: str):
    """Download best audio to downloads/ and return path + meta."""
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
        url = f"https://www.youtube.com/watch?v={vid}"

    outtmpl = os.path.join(DOWNLOADS_DIR, "%(id)s.%(ext)s")

    for client in PLAYER_CLIENTS:
        opts = _base_opts()
        opts.update({
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "extractor_args": {"youtube": {"player_client": [client]}},
            # Prefer audio-only containers
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "192",
            }],
            "keepvideo": False,
        })
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    continue
                # Find the downloaded file
                vid = info.get("id") or ""
                title = info.get("title") or "YouTube"
                duration = info.get("duration") or 0
                uploader = info.get("uploader") or ""

                # After FFmpegExtractAudio the file is usually .m4a
                candidates = [
                    os.path.join(DOWNLOADS_DIR, f"{vid}.m4a"),
                    os.path.join(DOWNLOADS_DIR, f"{vid}.webm"),
                    os.path.join(DOWNLOADS_DIR, f"{vid}.mp3"),
                    os.path.join(DOWNLOADS_DIR, f"{vid}.opus"),
                    os.path.join(DOWNLOADS_DIR, f"{vid}.mp4"),
                ]
                # Also check what ydl reports
                requested = info.get("requested_downloads") or []
                for rd in requested:
                    fp = rd.get("filepath")
                    if fp and os.path.isfile(fp):
                        candidates.insert(0, fp)
                if info.get("_filename") and os.path.isfile(info["_filename"]):
                    candidates.insert(0, info["_filename"])

                path = None
                for c in candidates:
                    if os.path.isfile(c):
                        path = c
                        break

                if path:
                    print(f"YT download OK client={client} path={path}")
                    return {
                        "path": path,
                        "title": title,
                        "duration": duration,
                        "uploader": uploader,
                        "webpage": info.get("webpage_url") or url,
                    }
        except Exception as e:
            print(f"YT download client={client}: {e}")
            continue

    # Fallback without postprocessor / with simpler format
    for client in PLAYER_CLIENTS:
        opts = _base_opts()
        opts.update({
            "format": "best",
            "outtmpl": outtmpl,
            "extractor_args": {"youtube": {"player_client": [client]}},
        })
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    continue
                vid = info.get("id") or ""
                title = info.get("title") or "YouTube"
                path = None
                for ext in ("m4a", "webm", "mp4", "mp3", "opus", "mkv"):
                    p = os.path.join(DOWNLOADS_DIR, f"{vid}.{ext}")
                    if os.path.isfile(p):
                        path = p
                        break
                if info.get("_filename") and os.path.isfile(info["_filename"]):
                    path = info["_filename"]
                if path:
                    print(f"YT download OK (fallback) client={client}")
                    return {
                        "path": path,
                        "title": title,
                        "duration": info.get("duration") or 0,
                        "uploader": info.get("uploader") or "",
                        "webpage": info.get("webpage_url") or url,
                    }
        except Exception as e:
            print(f"YT fallback client={client}: {e}")
            continue

    return None


# Keep old name for compatibility - now downloads instead of stream URL
def _get_stream_url_sync(url: str):
    result = _download_sync(url)
    if not result:
        return None
    # Map to shape expected by main (url key = local path for play_local_file)
    return {
        "url": result["path"],  # local path
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
