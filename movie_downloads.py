"""Safe async downloader for authorized direct movie media URLs."""

import asyncio
import errno
import hashlib
import ipaddress
import logging
import math
import os
import shutil
import socket
import time
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Awaitable, Callable, Optional
from urllib.parse import urljoin, urlsplit

import aiofiles
import aiohttp

from config import config

logger = logging.getLogger(__name__)
ProgressCallback = Callable[
    [int, Optional[int], float, Optional[float]], Awaitable[None]
]

_MEDIA_EXTENSIONS = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
    "video/quicktime": ".mov",
    "video/x-msvideo": ".avi",
    "video/mpeg": ".mpg",
    "video/mp2t": ".ts",
}
_ALLOWED_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".avi", ".mpg", ".mpeg", ".ts"}
_REDIRECT_CODES = {301, 302, 303, 307, 308}
_MAX_REDIRECTS = 5
_MAX_ATTEMPTS = 3
_RESERVE_BYTES = 64 * 1024 * 1024
_MAX_AUTOMATIC_RETRY_AFTER = 60
_DEFAULT_429_BACKOFF_SECONDS = 10


def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        seconds = float(value.strip())
        if math.isfinite(seconds) and seconds >= 0:
            return seconds
    except (AttributeError, ValueError):
        pass
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, retry_at.timestamp() - time.time())
    except (TypeError, ValueError, OverflowError, OSError):
        return None


class MovieDownloadError(Exception):
    """A user-safe download failure, optionally suitable for Retry."""

    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        rate_limited: bool = False,
        retry_after: Optional[float] = None,
    ):
        super().__init__(message)
        self.retryable = retryable
        self.rate_limited = rate_limited
        self.retry_after = retry_after


class MovieDownloadManager:
    """Download direct media asynchronously with host, size, and cache limits."""

    def __init__(self):
        self.directory = Path(config.MOVIE_DOWNLOAD_DIR).expanduser()
        self.allowed_hosts = set(config.MOVIE_ALLOWED_DOWNLOAD_HOSTS)
        logger.info(
            "Movie downloader approved hostnames: %s", sorted(self.allowed_hosts)
        )
        self.max_bytes = config.MOVIE_MAX_DOWNLOAD_MB * 1024 * 1024
        self.cache_ttl = config.MOVIE_CACHE_TTL_HOURS * 60 * 60
        self._semaphore = asyncio.Semaphore(config.MOVIE_MAX_CONCURRENT_DOWNLOADS)
        self._locks = {}
        self._active_parts = set()

    def _validate_url(self, url: str) -> str:
        if not isinstance(url, str) or not url:
            raise MovieDownloadError("The selected link is empty.")
        try:
            parsed = urlsplit(url)
            host = (
                (parsed.hostname or "")
                .encode("idna")
                .decode("ascii")
                .lower()
                .rstrip(".")
            )
            port = parsed.port
        except (UnicodeError, ValueError) as exc:
            raise MovieDownloadError("The selected media URL is malformed.") from exc
        if (
            parsed.scheme.lower() != "https"
            or not host
            or parsed.username
            or parsed.password
            or port not in (None, 443)
        ):
            raise MovieDownloadError("Only direct HTTPS media links are supported.")
        if host not in self.allowed_hosts:
            logger.warning(
                "Rejected movie download hostname %r; approved hostnames: %s",
                host,
                sorted(self.allowed_hosts),
            )
            raise MovieDownloadError(
                "This download host is not approved. Ask the bot owner to add its exact hostname to MOVIE_ALLOWED_DOWNLOAD_HOSTS."
            )
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return host
        if not address.is_global:
            raise MovieDownloadError(
                "Private or local-network download hosts are blocked."
            )
        return host

    async def _validate_public_dns(self, host: str, port: int) -> None:
        try:
            records = await asyncio.get_running_loop().getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
        except OSError as exc:
            raise MovieDownloadError(
                "Could not resolve the approved media host.", retryable=True
            ) from exc
        if not records:
            raise MovieDownloadError(
                "The approved media host did not resolve.", retryable=True
            )
        for record in records:
            address = ipaddress.ip_address(record[4][0])
            if not address.is_global:
                raise MovieDownloadError(
                    "The media host resolved to a private address and was blocked."
                )

    def _prepare_directory(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)

    def _find_cached_sync(self, digest: str) -> Optional[str]:
        for candidate in self.directory.glob(f"{digest}.*"):
            if candidate.suffix == ".part":
                continue
            try:
                stat = candidate.stat()
                if (
                    candidate.is_file()
                    and stat.st_size > 0
                    and time.time() - stat.st_mtime <= self.cache_ttl
                ):
                    return str(candidate)
            except OSError:
                continue
        return None

    def _cleanup_sync(
        self, protected_paths: set, active_parts: set, target_free: int
    ) -> None:
        now = time.time()
        protected = {os.path.abspath(path) for path in protected_paths}
        active = {os.path.abspath(path) for path in active_parts}
        candidates = []
        for path in self.directory.iterdir():
            if not path.is_file():
                continue
            absolute = os.path.abspath(path)
            if absolute in protected or absolute in active:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            age = now - stat.st_mtime
            if path.suffix == ".part":
                if age > 6 * 60 * 60:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        logger.warning(
                            "Unable to remove stale partial movie file %s", path
                        )
                continue
            if age > self.cache_ttl:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Unable to remove expired movie cache file %s", path)
                continue
            candidates.append((stat.st_mtime, path))

        for _, path in sorted(candidates):
            try:
                if shutil.disk_usage(self.directory).free >= target_free:
                    break
                path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Unable to evict movie cache file %s", path)

    async def _cleanup(self, protected_paths: set, required_bytes: int = 0) -> None:
        await asyncio.to_thread(self._prepare_directory)
        target_free = max(_RESERVE_BYTES, required_bytes + _RESERVE_BYTES)
        await asyncio.to_thread(
            self._cleanup_sync,
            set(protected_paths),
            set(self._active_parts),
            target_free,
        )
        free_bytes = await asyncio.to_thread(shutil.disk_usage, self.directory)
        if free_bytes.free < target_free:
            raise MovieDownloadError(
                "There is not enough free storage for this download. Try a smaller quality or ask the bot owner to free space."
            )

    @staticmethod
    def _extension(content_type: str, url: str) -> str:
        content_type = (content_type or "").split(";", 1)[0].strip().lower()
        if content_type in _MEDIA_EXTENSIONS:
            return _MEDIA_EXTENSIONS[content_type]
        if content_type in {"application/octet-stream", ""}:
            suffix = Path(urlsplit(url).path).suffix.lower()
            if suffix in _ALLOWED_EXTENSIONS:
                return suffix
        if content_type.startswith("text/") or "html" in content_type:
            raise MovieDownloadError(
                "The selected URL serves a webpage, not a supported direct media file. A provider-specific resolver is not configured."
            )
        raise MovieDownloadError(
            "The selected URL is not a supported video file (MP4, WebM, MKV, MOV, AVI, MPEG, or TS)."
        )

    async def _request_response(self, session: aiohttp.ClientSession, initial_url: str):
        current_url = initial_url
        for _ in range(_MAX_REDIRECTS + 1):
            host = self._validate_url(current_url)
            parsed = urlsplit(current_url)
            await self._validate_public_dns(host, parsed.port or 443)
            response = await session.get(
                current_url,
                allow_redirects=False,
                headers={
                    "Accept": "video/*,application/octet-stream",
                    "User-Agent": "MASTER-MUSIC-BOT/1.0",
                },
            )
            if response.status not in _REDIRECT_CODES:
                return response, current_url
            location = response.headers.get("Location")
            response.release()
            if not location:
                raise MovieDownloadError(
                    "The media source returned an invalid redirect."
                )
            current_url = urljoin(current_url, location)
        raise MovieDownloadError("The media source redirected too many times.")

    async def _download_once(
        self,
        url: str,
        digest: str,
        progress: Optional[ProgressCallback],
        protected_paths: set,
    ) -> str:
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=90)
        connector = aiohttp.TCPConnector(ssl=True)
        async with aiohttp.ClientSession(
            timeout=timeout, connector=connector, trust_env=False
        ) as session:
            response, final_url = await self._request_response(session, url)
            try:
                if response.status in {403, 404, 410}:
                    raise MovieDownloadError(
                        "This media link has expired or is unavailable. Return to results and choose another link."
                    )
                if response.status == 429:
                    retry_after = _retry_after_seconds(
                        response.headers.get("Retry-After")
                    )
                    host = urlsplit(final_url).hostname or "<unknown>"
                    logger.warning(
                        "Movie media host %s returned HTTP 429; retry-after-seconds=%s",
                        host,
                        (
                            retry_after
                            if retry_after is not None
                            else "not provided/invalid"
                        ),
                    )
                    retry_hint = (
                        f" Retry after at least {math.ceil(retry_after)} seconds."
                        if retry_after is not None
                        else " Please retry later."
                    )
                    raise MovieDownloadError(
                        "The media host returned HTTP 429 and is rate-limiting downloads."
                        + retry_hint,
                        retryable=True,
                        rate_limited=True,
                        retry_after=retry_after,
                    )
                if response.status >= 500:
                    raise MovieDownloadError(
                        f"The media host returned HTTP {response.status}; you can retry shortly.",
                        retryable=True,
                    )
                if response.status != 200:
                    raise MovieDownloadError(
                        f"The media host returned HTTP {response.status}."
                    )

                content_type = response.headers.get("Content-Type", "")
                extension = self._extension(content_type, final_url)
                total = response.content_length
                if total is not None and total > self.max_bytes:
                    raise MovieDownloadError(
                        f"The selected file exceeds the configured {config.MOVIE_MAX_DOWNLOAD_MB} MiB limit."
                    )
                await self._cleanup(protected_paths, total or 0)
                target = self.directory / f"{digest}{extension}"
                part = (
                    self.directory
                    / f"{digest}.{asyncio.current_task().get_name()}.part"
                )
                part_path = os.path.abspath(part)
                self._active_parts.add(part_path)
                started = time.monotonic()
                downloaded = 0
                last_progress = started
                first_bytes = bytearray()
                try:
                    async with aiofiles.open(part, "wb") as output:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            if not first_bytes:
                                first_bytes.extend(chunk[:512])
                                prefix = bytes(first_bytes).lstrip().lower()
                                if prefix.startswith(
                                    (b"<!doctype html", b"<html", b"<head", b"<script")
                                ):
                                    raise MovieDownloadError(
                                        "The selected link returned HTML instead of playable media."
                                    )
                            downloaded += len(chunk)
                            if downloaded > self.max_bytes:
                                raise MovieDownloadError(
                                    f"The file exceeded the configured {config.MOVIE_MAX_DOWNLOAD_MB} MiB limit."
                                )
                            await output.write(chunk)
                            now = time.monotonic()
                            if now - last_progress >= 2:
                                free_bytes = await asyncio.to_thread(
                                    shutil.disk_usage, self.directory
                                )
                                if free_bytes.free < _RESERVE_BYTES:
                                    await self._cleanup(protected_paths, len(chunk))
                                elapsed = max(now - started, 0.001)
                                speed = downloaded / elapsed
                                eta = (
                                    (total - downloaded) / speed
                                    if total and speed > 0
                                    else None
                                )
                                if progress:
                                    try:
                                        await progress(downloaded, total, speed, eta)
                                    except Exception:
                                        logger.exception(
                                            "Movie progress callback failed"
                                        )
                                last_progress = now
                    if downloaded == 0:
                        raise MovieDownloadError("The selected media file was empty.")
                    if total is not None and downloaded != total:
                        raise MovieDownloadError(
                            "The download ended before the complete file arrived.",
                            retryable=True,
                        )
                    await asyncio.to_thread(os.replace, part, target)
                    elapsed = max(time.monotonic() - started, 0.001)
                    if progress:
                        try:
                            await progress(downloaded, total, downloaded / elapsed, 0.0)
                        except Exception:
                            logger.exception("Movie final progress callback failed")
                    return str(target)
                except OSError as exc:
                    if exc.errno == errno.ENOSPC:
                        raise MovieDownloadError(
                            "The server ran out of storage during download; old cache files were cleaned."
                        ) from exc
                    raise MovieDownloadError(
                        "The server could not write the downloaded file."
                    ) from exc
                finally:
                    self._active_parts.discard(part_path)
                    try:
                        part.unlink(missing_ok=True)
                    except OSError:
                        logger.warning(
                            "Unable to remove partial movie download %s", part
                        )
            finally:
                response.release()

    async def download(
        self,
        url: str,
        *,
        progress: Optional[ProgressCallback] = None,
        protected_paths: Optional[set] = None,
    ) -> str:
        """Return a cached or newly downloaded, validated direct-media path."""
        self._validate_url(url)
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        protected_paths = protected_paths or set()
        lock = self._locks.setdefault(digest, asyncio.Lock())
        async with self._semaphore, lock:
            await asyncio.to_thread(self._prepare_directory)
            cached = await asyncio.to_thread(self._find_cached_sync, digest)
            if cached:
                return cached
            await self._cleanup(protected_paths)

            last_error = None
            for attempt in range(_MAX_ATTEMPTS):
                delay = 0.0
                try:
                    path = await self._download_once(
                        url, digest, progress, protected_paths
                    )
                    await self._cleanup(protected_paths | {path})
                    return path
                except MovieDownloadError as exc:
                    last_error = exc
                    if not exc.retryable or attempt == _MAX_ATTEMPTS - 1:
                        raise
                    if exc.rate_limited:
                        if exc.retry_after is not None:
                            if exc.retry_after > _MAX_AUTOMATIC_RETRY_AFTER:
                                raise MovieDownloadError(
                                    "The media host asked the bot to wait at least "
                                    f"{math.ceil(exc.retry_after)} seconds before retrying.",
                                    retryable=True,
                                    rate_limited=True,
                                    retry_after=exc.retry_after,
                                ) from exc
                            delay = exc.retry_after
                        else:
                            delay = min(_DEFAULT_429_BACKOFF_SECONDS * (2**attempt), 60)
                    else:
                        delay = min(2**attempt, 4)
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = MovieDownloadError(
                        "Temporary network error while downloading media.",
                        retryable=True,
                    )
                    if attempt == _MAX_ATTEMPTS - 1:
                        raise last_error from exc
                    delay = min(2**attempt, 4)
                await asyncio.sleep(delay)
            if last_error:
                raise last_error
            raise MovieDownloadError("The download failed for an unknown reason.")

    async def cleanup(self, protected_paths: Optional[set] = None) -> None:
        """Remove expired cache files while preserving current/queued media paths."""
        await self._cleanup(protected_paths or set())
