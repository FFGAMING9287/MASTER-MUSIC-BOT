"""
Movie Downloader API integration for Music Player
Uses https://movie-downloader-api.vercel.app
"""

import aiohttp
import asyncio
import os
from typing import Optional, Dict

API_BASE = "https://movie-downloader-api.vercel.app/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

async def search_movie(query: str) -> Optional[Dict]:
    """Search movies/TV shows by query."""
    url = f"{API_BASE}/search?q={query}"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                print(f"Search status: {resp.status}")
                return None
    except Exception as e:
        print(f"Movie search error: {e}")
        return None

async def download_movie(download_url: str, filename: str) -> Optional[str]:
    """Download movie/episode to downloads/ folder. Returns local path."""
    os.makedirs("downloads", exist_ok=True)
    # Clean filename
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)
    local_path = f"downloads/{safe_name}"

    try:
        timeout = aiohttp.ClientTimeout(total=600, connect=30, sock_read=120)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
            # allow_redirects=True is default
            async with session.get(download_url, allow_redirects=True) as resp:
                print(f"Download status: {resp.status}, final URL: {resp.url}")
                if resp.status != 200:
                    text = await resp.text()
                    print(f"Download failed body (first 300): {text[:300]}")
                    return None

                # Check content type roughly
                content_type = resp.headers.get("Content-Type", "")
                print(f"Content-Type: {content_type}")

                total = 0
                with open(local_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 128):
                        if not chunk:
                            break
                        f.write(chunk)
                        total += len(chunk)

                print(f"Downloaded {total} bytes to {local_path}")
                if total < 10000:  # too small = probably error page
                    print("File too small, likely failed")
                    try:
                        os.remove(local_path)
                    except:
                        pass
                    return None
                return local_path
    except Exception as e:
        print(f"Download error: {type(e).__name__}: {e}")
        return None
