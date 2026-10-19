"""
YouTube via Piped + Invidious
Download audio to local file so VC always has real sound.
"""

import asyncio
import os
import re

import aiohttp

from core.settings_store import (
    create_cookie_tempfile,
    delete_cookie_tempfile,
    get_api_urls,
    has_cookie,
)

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://pipedapi.ducks.party",
    "https://api.piped.private.coffee",
    "https://pipedapi.lunar.icu",
]

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.flokinet.to",
    "https://invidious.private.coffee",
    "https://yewtu.be",
    "https://vid.puffyan.us",
]

DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

UA = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"


def _yt_dlp_options(cookie_path=None):
    options = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }
    if cookie_path:
        options["cookiefile"] = cookie_path
    return options


def _yt_dlp_search(query: str, limit: int):
    cookie_path = create_cookie_tempfile("youtube")
    try:
        from yt_dlp import YoutubeDL

        options = _yt_dlp_options(cookie_path)
        options["extract_flat"] = "in_playlist"
        options["playlistend"] = limit
        with YoutubeDL(options) as ydl:
            result = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
        entries = (result or {}).get("entries") or []
        output = []
        for entry in entries[:limit]:
            if not isinstance(entry, dict):
                continue
            video_id = entry.get("id") or ""
            if not video_id:
                continue
            output.append(
                {
                    "id": video_id,
                    "title": entry.get("title") or "Unknown",
                    "duration": entry.get("duration") or 0,
                    "uploader": entry.get("uploader") or entry.get("channel") or "",
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumb": entry.get("thumbnail")
                    or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                }
            )
        return output
    except Exception as exc:
        print(f"yt-dlp search fallback failed: {type(exc).__name__}")
        return []
    finally:
        delete_cookie_tempfile(cookie_path)


def _yt_dlp_stream(url: str):
    cookie_path = create_cookie_tempfile("youtube")
    try:
        from yt_dlp import YoutubeDL

        options = _yt_dlp_options(cookie_path)
        options["format"] = "bestaudio/best"
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            return None
        stream_url = info.get("url")
        formats = info.get("requested_formats") or []
        if not stream_url and formats:
            audio = next(
                (item for item in formats if item.get("acodec") != "none"), None
            )
            stream_url = audio.get("url") if audio else None
        if not stream_url:
            return None
        return {
            "url": stream_url,
            "title": info.get("title") or "YouTube",
            "duration": info.get("duration") or 0,
            "uploader": info.get("uploader") or info.get("channel") or "",
            "mime": info.get("format_note") or "audio",
            "is_local": False,
        }
    except Exception as exc:
        print(f"yt-dlp stream fallback failed: {type(exc).__name__}")
        return None
    finally:
        delete_cookie_tempfile(cookie_path)


def extract_video_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    m = re.search(r"(?:v=|/shorts/|youtu\.be/)([\w-]{11})", s)
    if m:
        return m.group(1)
    m = re.search(r"([\w-]{11})", s)
    return m.group(1) if m else ""


async def _get_json(session, url, timeout=15):
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={"User-Agent": UA},
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"GET fail {url}: {e}")
    return None


async def search_youtube(query: str, limit: int = 6):
    results = []
    if has_cookie("youtube"):
        cookie_results = await asyncio.to_thread(_yt_dlp_search, query, limit)
        if cookie_results:
            return cookie_results
    async with aiohttp.ClientSession() as session:
        for base in get_api_urls("piped", PIPED_INSTANCES):
            data = await _get_json(
                session, f"{base}/search?q={aiohttp.helpers.quote(query)}&filter=videos"
            )
            if not data or not isinstance(data, list):
                if isinstance(data, dict):
                    data = data.get("items") or data.get("results") or []
                else:
                    continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                if item.get("type") and item.get("type") not in (
                    "stream",
                    "video",
                    None,
                ):
                    continue
                vid = (
                    item.get("url", "").split("watch?v=")[-1].split("&")[0]
                    if item.get("url")
                    else item.get("id") or ""
                )
                if not vid or len(vid) < 10:
                    vid = (item.get("url") or "").rstrip("/").split("/")[-1]
                if not vid:
                    continue
                title = item.get("title") or "Unknown"
                duration = item.get("duration") or 0
                uploader = item.get("uploader") or item.get("uploaderName") or ""
                results.append(
                    {
                        "id": vid,
                        "title": title,
                        "duration": duration,
                        "uploader": uploader,
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "thumb": item.get("thumbnail")
                        or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    }
                )
                if len(results) >= limit:
                    return results
            if results:
                return results

        for base in get_api_urls("invidious", INVIDIOUS_INSTANCES):
            data = await _get_json(
                session,
                f"{base}/api/v1/search?q={aiohttp.helpers.quote(query)}&type=video",
            )
            if not data or not isinstance(data, list):
                continue
            for item in data:
                vid = item.get("videoId") or ""
                if not vid:
                    continue
                results.append(
                    {
                        "id": vid,
                        "title": item.get("title") or "Unknown",
                        "duration": item.get("lengthSeconds") or 0,
                        "uploader": item.get("author") or "",
                        "url": f"https://www.youtube.com/watch?v={vid}",
                        "thumb": (item.get("videoThumbnails") or [{}])[0].get("url")
                        or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    }
                )
                if len(results) >= limit:
                    return results
            if results:
                return results
    if not results:
        return await asyncio.to_thread(_yt_dlp_search, query, limit)
    return results


def _pick_audio_url(streams: list):
    if not streams:
        return None

    def score(s):
        mime = (s.get("mimeType") or s.get("type") or "").lower()
        br = int(s.get("bitrate") or 0)
        sc = br
        if "mp4" in mime or "m4a" in mime or "audio/mp4" in mime:
            sc += 200000
        if "webm" in mime or "opus" in mime:
            sc += 100000
        if "audio" in mime:
            sc += 50000
        return sc

    ranked = sorted(streams, key=score, reverse=True)
    for s in ranked:
        u = s.get("url")
        if u:
            return u, (s.get("mimeType") or s.get("type") or "")
    return None, ""


async def _streams_piped(session, vid: str):
    for base in get_api_urls("piped", PIPED_INSTANCES):
        data = await _get_json(session, f"{base}/streams/{vid}")
        if not data:
            continue
        title = data.get("title") or "YouTube"
        duration = data.get("duration") or 0
        uploader = data.get("uploader") or ""
        audios = data.get("audioStreams") or []
        url, mime = _pick_audio_url(audios)
        if not url:
            for v in data.get("videoStreams") or []:
                if v.get("url") and not v.get("videoOnly"):
                    url = v["url"]
                    mime = v.get("mimeType") or ""
                    break
        if url:
            print(f"Piped OK {base} vid={vid}")
            return {
                "url": url,
                "title": title,
                "duration": duration,
                "uploader": uploader,
                "mime": mime,
                "is_local": False,
            }
    return None


async def _streams_invidious(session, vid: str):
    for base in get_api_urls("invidious", INVIDIOUS_INSTANCES):
        data = await _get_json(session, f"{base}/api/v1/videos/{vid}")
        if not data:
            continue
        title = data.get("title") or "YouTube"
        duration = data.get("lengthSeconds") or 0
        uploader = data.get("author") or ""
        formats = data.get("adaptiveFormats") or []
        audio_fmts = [f for f in formats if "audio" in (f.get("type") or "")]
        url, mime = _pick_audio_url(audio_fmts)
        if not url:
            for f in data.get("formatStreams") or []:
                if f.get("url"):
                    url = f["url"]
                    mime = f.get("type") or ""
                    break
        if url:
            print(f"Invidious OK {base} vid={vid}")
            return {
                "url": url,
                "title": title,
                "duration": duration,
                "uploader": uploader,
                "mime": mime,
                "is_local": False,
            }
    return None


async def _download_audio(url: str, vid: str, mime: str = "") -> str | None:
    """Download stream URL to local file for reliable VC playback."""
    ext = "m4a"
    m = (mime or "").lower()
    if "webm" in m or "opus" in m:
        ext = "webm"
    elif "mp4" in m or "m4a" in m:
        ext = "m4a"
    path = os.path.join(DOWNLOADS_DIR, f"yt_{vid}.{ext}")
    if os.path.exists(path) and os.path.getsize(path) > 50000:
        return path

    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Referer": "https://www.youtube.com/",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=180, sock_read=60)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    print(f"audio dl status {resp.status}")
                    return None
                total = 0
                with open(path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(64 * 1024):
                        if not chunk:
                            break
                        f.write(chunk)
                        total += len(chunk)
                if total < 20000:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                    print(f"audio too small {total}")
                    return None
                print(f"Downloaded audio {total} bytes -> {path}")
                return path
    except Exception as e:
        print(f"audio download error: {e}")
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
        return None


async def get_stream_info(url: str):
    """Resolve YouTube → prefer local audio file for VC sound."""
    vid = extract_video_id(url)
    if not vid:
        return None

    info = None
    if has_cookie("youtube"):
        info = await asyncio.to_thread(_yt_dlp_stream, url)
    if not info:
        async with aiohttp.ClientSession() as session:
            info = await _streams_piped(session, vid)
            if not info:
                info = await _streams_invidious(session, vid)
    if not info:
        info = await asyncio.to_thread(_yt_dlp_stream, url)
        if not info:
            print(f"No stream for {vid}")
            return None

    # Download to local so pytgcalls always has audio
    local = await _download_audio(info["url"], vid, info.get("mime") or "")
    if local:
        return {
            "url": local,
            "path": local,
            "title": info.get("title") or "YouTube",
            "duration": info.get("duration") or 0,
            "uploader": info.get("uploader") or "",
            "is_local": True,
            "thumb": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        }

    # Fallback remote URL (may be silent on some hosts)
    info["is_local"] = False
    info["thumb"] = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return info
