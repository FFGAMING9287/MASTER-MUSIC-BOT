"""
Movie Downloader API integration for Music Player
Uses https://movie-downloader-api.vercel.app
"""

import aiohttp
import asyncio
from typing import Optional, List, Dict

API_BASE = "https://movie-downloader-api.vercel.app/api"

async def search_movie(query: str) -> Optional[Dict]:
    """Search movies/TV shows by query."""
    url = f"{API_BASE}/search?q={query}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                return None
    except Exception as e:
        print(f"Movie search error: {e}")
        return None

async def download_movie(download_url: str, filename: str) -> Optional[str]:
    """Download movie/episode to downloads/ folder. Returns local path."""
    import os
    os.makedirs("downloads", exist_ok=True)
    local_path = f"downloads/{filename}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url, timeout=300) as resp:
                if resp.status == 200:
                    with open(local_path, "wb") as f:
                        while True:
                            chunk = await resp.content.read(1024 * 64)
                            if not chunk:
                                break
                            f.write(chunk)
                    return local_path
                return None
    except Exception as e:
        print(f"Download error: {e}")
        return None
