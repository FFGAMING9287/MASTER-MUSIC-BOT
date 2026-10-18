"""
Movie + Adult Downloader API integration
- movie-downloader-api.vercel.app (normal movies)
- fulux-downloader-api.vercel.app (adult content)
"""

import aiohttp
import asyncio
import os
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse

MOVIE_API = "https://movie-downloader-api.vercel.app/api"
FULUX_API = "https://fulux-downloader-api.vercel.app/api"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

async def search_movie(query: str) -> Optional[Dict]:
    """Normal movie/TV search"""
    url = f"{MOVIE_API}/search"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
            async with session.get(url, params={"q": query}) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
    except Exception as e:
        print(f"Movie search error: {e}")
        return None

async def search_adult(query: str) -> Optional[Dict]:
    """Adult content search using Fulux API"""
    url = f"{FULUX_API}/search?q={query}"
    try:
        timeout = aiohttp.ClientTimeout(total=25)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data
                print(f"Fulux status: {resp.status}")
                return None
    except Exception as e:
        print(f"Adult search error: {e}")
        return None

# Serialize downloads in this process to avoid burst traffic from one Railway instance.
_DOWNLOAD_SEMAPHORE = asyncio.Semaphore(1)
DOWNLOAD_RETRIES = max(0, min(3, int(os.getenv("MOVIE_DOWNLOAD_RETRIES", "2"))))
MAX_AUTOMATIC_RETRY_WAIT = max(0, min(300, int(os.getenv("MOVIE_MAX_RETRY_WAIT", "120"))))


def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
    """Parse Retry-After as seconds or an HTTP date."""
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except (TypeError, ValueError):
        pass
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, retry_at.timestamp() - time.time())
    except (TypeError, ValueError, OverflowError):
        return None


def _safe_filename(filename: str) -> str:
    name = "".join(c if c.isalnum() or c in "._-" else "_" for c in filename)[:100]
    return name or "movie_download.mp4"


async def download_file(download_url: str, filename: str) -> Tuple[Optional[str], Optional[str]]:
    """Download media with bounded 429/5xx retries; return (path, final_url) or (None, error)."""
    os.makedirs("downloads", exist_ok=True)
    local_path = os.path.join("downloads", _safe_filename(filename))
    timeout = aiohttp.ClientTimeout(total=900, connect=30, sock_read=120)

    async with _DOWNLOAD_SEMAPHORE:
        try:
            async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as session:
                for attempt in range(DOWNLOAD_RETRIES + 1):
                    retry_delay = None
                    retry_reason = None

                    async with session.get(download_url, allow_redirects=True) as resp:
                        final_url = str(resp.url)
                        host = urlparse(final_url).netloc
                        content_type = resp.headers.get("Content-Type", "unknown")
                        print(
                            f"Movie download: HTTP {resp.status}; host={host}; "
                            f"type={content_type}; attempt={attempt + 1}/{DOWNLOAD_RETRIES + 1}"
                        )

                        if resp.status == 429:
                            retry_delay = _retry_after_seconds(resp.headers.get("Retry-After"))
                            if retry_delay is None:
                                retry_delay = min(5 * (2 ** attempt), 30)
                            retry_reason = f"HTTP 429 from {host}"
                            if attempt >= DOWNLOAD_RETRIES or retry_delay > MAX_AUTOMATIC_RETRY_WAIT:
                                wait_text = f"{retry_delay:.0f}s"
                                return None, (
                                    f"CDN/provider rate limit (429) from {host}. "
                                    f"Retry after {wait_text}; automatic retries stopped. "
                                    "Please wait before trying again."
                                )
                            body = (await resp.content.read(400)).decode("utf-8", "replace").replace("\n", " ")
                            print(f"{retry_reason}; retry in {retry_delay:.1f}s; body={body[:250]}")
                        elif resp.status in (500, 502, 503, 504):
                            if attempt >= DOWNLOAD_RETRIES:
                                body = (await resp.content.read(400)).decode("utf-8", "replace").replace("\n", " ")
                                return None, f"Temporary server error HTTP {resp.status} from {host}: {body[:200]}"
                            retry_delay = min(2 ** (attempt + 1), 15)
                            retry_reason = f"HTTP {resp.status} from {host}"
                            print(f"{retry_reason}; retry in {retry_delay:.1f}s")
                        elif resp.status != 200:
                            body = (await resp.content.read(400)).decode("utf-8", "replace").replace("\n", " ")
                            return None, (
                                f"Download endpoint returned HTTP {resp.status} from {host} "
                                f"(Content-Type: {content_type}). Response: {body[:200]}"
                            )
                        elif "text/html" in content_type.lower():
                            body = (await resp.content.read(400)).decode("utf-8", "replace").replace("\n", " ")
                            return None, f"Expected video but received HTML from {host}: {body[:200]}"
                        else:
                            total = 0
                            try:
                                with open(local_path, "wb") as file:
                                    async for chunk in resp.content.iter_chunked(1024 * 128):
                                        if chunk:
                                            file.write(chunk)
                                            total += len(chunk)
                            except Exception:
                                try:
                                    os.remove(local_path)
                                except OSError:
                                    pass
                                raise

                            if total < 30000:
                                try:
                                    os.remove(local_path)
                                except OSError:
                                    pass
                                return None, (
                                    f"Downloaded response was too small ({total} bytes) from {host}; "
                                    "provider may have returned an error page or incomplete file."
                                )

                            print(f"Movie download complete: {total} bytes from {host}")
                            return local_path, final_url

                    if retry_delay is not None:
                        print(f"Waiting {retry_delay:.1f}s before retry ({retry_reason})")
                        await asyncio.sleep(retry_delay)
                        continue

                return None, "Download failed after retries."

        except asyncio.TimeoutError:
            try:
                os.remove(local_path)
            except OSError:
                pass
            return None, "Download timed out. Try again later; repeated immediate retries may trigger provider limits."
        except aiohttp.ClientError as e:
            try:
                os.remove(local_path)
            except OSError:
                pass
            print(f"Download network error: {type(e).__name__}: {e}")
            return None, f"Network error while downloading: {type(e).__name__}: {e}"
        except Exception as e:
            try:
                os.remove(local_path)
            except OSError:
                pass
            print(f"Download error: {type(e).__name__}: {e}")
            return None, f"Download error: {type(e).__name__}: {e}"


# Keep old name for compatibility
async def download_movie(download_url: str, filename: str):
    return await download_file(download_url, filename)
