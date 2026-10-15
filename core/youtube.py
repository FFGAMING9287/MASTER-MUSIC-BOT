"""
YouTube via Piped + Invidious (works from cloud IPs)
yt-dlp is blocked on Railway — these APIs proxy streams.
"""

import asyncio
import os
import re
import aiohttp

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
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), headers={"User-Agent": UA}) as r:
            if r.status == 200:
                return await r.json()
    except Exception as e:
        print(f"GET fail {url}: {e}")
    return None


async def search_youtube(query: str, limit: int = 6):
    """Search via Piped (fallback Invidious)."""
    results = []
    async with aiohttp.ClientSession() as session:
        for base in PIPED_INSTANCES:
            data = await _get_json(session, f"{base}/search?q={aiohttp.helpers.quote(query)}&filter=videos")
            if not data or not isinstance(data, list):
                # some return {items: [...]}
                if isinstance(data, dict):
                    data = data.get("items") or data.get("results") or []
                else:
                    continue
            for item in data:
                if not isinstance(item, dict):
                    continue
                if item.get("type") and item.get("type") not in ("stream", "video", None):
                    continue
                vid = item.get("url", "").split("watch?v=")[-1].split("&")[0] if item.get("url") else item.get("id") or ""
                if not vid or len(vid) < 10:
                    vid = (item.get("url") or "").rstrip("/").split("/")[-1]
                if not vid:
                    continue
                title = item.get("title") or "Unknown"
                duration = item.get("duration") or 0
                uploader = item.get("uploaderName") or item.get("uploader") or ""
                results.append({
                    "id": vid,
                    "title": title,
                    "duration": duration,
                    "uploader": uploader,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "thumb": item.get("thumbnail") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                })
                if len(results) >= limit:
                    return results
            if results:
                return results

        # Invidious search
        for base in INVIDIOUS_INSTANCES:
            data = await _get_json(session, f"{base}/api/v1/search?q={aiohttp.helpers.quote(query)}&type=video")
            if not data or not isinstance(data, list):
                continue
            for item in data:
                vid = item.get("videoId") or ""
                if not vid:
                    continue
                results.append({
                    "id": vid,
                    "title": item.get("title") or "Unknown",
                    "duration": item.get("lengthSeconds") or 0,
                    "uploader": item.get("author") or "",
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "thumb": (item.get("videoThumbnails") or [{}])[0].get("url") or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                })
                if len(results) >= limit:
                    return results
            if results:
                return results
    return results


def _pick_audio_url(streams: list) -> str | None:
    if not streams:
        return None
    # Prefer m4a / mp4 audio, higher bitrate
    def score(s):
        mime = (s.get("mimeType") or s.get("type") or "").lower()
        br = int(s.get("bitrate") or 0)
        sc = br
        if "mp4" in mime or "m4a" in mime:
            sc += 100000
        if "audio" in mime:
            sc += 50000
        return sc
    ranked = sorted(streams, key=score, reverse=True)
    for s in ranked:
        u = s.get("url")
        if u:
            return u
    return None


async def _streams_piped(session, vid: str):
    for base in PIPED_INSTANCES:
        data = await _get_json(session, f"{base}/streams/{vid}")
        if not data:
            continue
        title = data.get("title") or "YouTube"
        duration = data.get("duration") or 0
        uploader = data.get("uploader") or ""
        audios = data.get("audioStreams") or []
        url = _pick_audio_url(audios)
        if not url:
            # fallback any video stream with audio
            for v in (data.get("videoStreams") or []):
                if v.get("url") and not v.get("videoOnly"):
                    url = v["url"]
                    break
        if url:
            print(f"Piped OK {base} vid={vid}")
            return {"url": url, "title": title, "duration": duration, "uploader": uploader, "is_local": False}
    return None


async def _streams_invidious(session, vid: str):
    for base in INVIDIOUS_INSTANCES:
        data = await _get_json(session, f"{base}/api/v1/videos/{vid}")
        if not data:
            continue
        title = data.get("title") or "YouTube"
        duration = data.get("lengthSeconds") or 0
        uploader = data.get("author") or ""
        formats = data.get("adaptiveFormats") or []
        audio_fmts = [f for f in formats if "audio" in (f.get("type") or "")]
        url = _pick_audio_url(audio_fmts)
        if not url:
            # progressive
            for f in (data.get("formatStreams") or []):
                if f.get("url"):
                    url = f["url"]
                    break
        if url:
            print(f"Invidious OK {base} vid={vid}")
            return {"url": url, "title": title, "duration": duration, "uploader": uploader, "is_local": False}
    return None


async def get_stream_info(url: str):
    vid = extract_video_id(url)
    if not vid:
        return None
    async with aiohttp.ClientSession() as session:
        info = await _streams_piped(session, vid)
        if info:
            return info
        info = await _streams_invidious(session, vid)
        if info:
            return info
    print(f"No stream for {vid}")
    return None
