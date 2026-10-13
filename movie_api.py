"""
Movie Downloader API integration for Music Player
Uses https://movie-downloader-api.vercel.app
"""

import aiohttp
import asyncio
import os
from typing import Optional, Dict, Tuple

API_BASE = "https://movie-downloader-api.vercel.app/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://movie-downloader-api.vercel.app/",
}

async def search_movie(query: str) -> Optional[Dict]:
    url = f"{API_BASE}/search?q={query}"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except Exception as e:
        print(f"Movie search error: {e}")
        return None

async def download_movie(download_url: str, filename: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (local_path, error_message_or_final_url)"""
    os.makedirs("downloads", exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    local_path = f"downloads/{safe_name}"

    try:
        timeout = aiohttp.ClientTimeout(total=600, connect=30, sock_read=120)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
            async with session.get(download_url, allow_redirects=True) as resp:
                final_url = str(resp.url)
                print(f"Download status: {resp.status}, final: {final_url}")

                if resp.status == 429:
                    return None, "CDN is rate-limiting right now (429). Wait 1-2 minutes and try again."

                if resp.status != 200:
                    return None, f"Server returned HTTP {resp.status}"

                total = 0
                with open(local_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 128):
                        if not chunk:
                            break
                        f.write(chunk)
                        total += len(chunk)

                if total < 50000:
                    try:
                        os.remove(local_path)
                    except:
                        pass
                    return None, "Downloaded file too small (probably blocked by CDN)"

                return local_path, final_url

    except asyncio.TimeoutError:
        return None, "Download timed out (file may be large)"
    except Exception as e:
        print(f"Download error: {e}")
        return None, str(e)
