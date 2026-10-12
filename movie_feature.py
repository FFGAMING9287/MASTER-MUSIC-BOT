"""Movie episode callbacks and playback orchestration for the existing bot."""

import asyncio
import html
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from pyrogram import enums, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from pytgcalls.exceptions import NoActiveGroupCall, NotInCallError

from config import config
from core import all_groups, get_group, get_queue, set_group, start_stream
from core.song import Song
from lang import load
from movie_downloads import MovieDownloadError, MovieDownloadManager
from movie_handler import (
    create_movie_keyboard,
    cycle_movie_filter,
    get_movie_selection,
    get_movie_session,
    reset_movie_filters,
    set_movie_page,
)

logger = logging.getLogger(__name__)


@dataclass
class MovieJob:
    job_id: str
    chat_id: int
    requester_id: int
    requester: object
    selection: Dict
    result_message: Message
    status_message: Message
    state: str = "downloading"
    bytes_downloaded: int = 0
    total_bytes: Optional[int] = None
    speed: float = 0.0
    eta: Optional[float] = None
    path: Optional[str] = None
    song: Optional[Song] = None
    task: Optional[asyncio.Task] = None
    retryable: bool = False
    failure_message: str = ""
    queue_position: Optional[int] = None
    created_at: float = field(default_factory=time.time)
    last_update: float = 0.0


class MovieFeature:
    """Registers movie callbacks and reuses the bot's existing voice-chat queue."""

    def __init__(self, client):
        self.client = client
        self.downloader = MovieDownloadManager()
        self.jobs: Dict[str, MovieJob] = {}
        self.chat_locks = {}
        self.cleanup_task = None

    def register(self) -> None:
        self.client.on_callback_query(filters.regex(r"^movie:"))(self.handle_callback)

    @staticmethod
    def _bytes(value: Optional[float]) -> str:
        if value is None:
            return "unknown"
        amount = float(value)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if amount < 1024 or unit == "TiB":
                return f"{amount:.1f} {unit}"
            amount /= 1024
        return f"{amount:.1f} TiB"

    @staticmethod
    def _duration(seconds: Optional[float]) -> str:
        if seconds is None:
            return "unknown"
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return (
            f"{hours}:{minutes:02d}:{seconds:02d}"
            if hours
            else f"{minutes}:{seconds:02d}"
        )

    @staticmethod
    def _selection_label(selection: Dict) -> str:
        parts = [str(selection.get("title") or "Untitled")]
        season = selection.get("season")
        episode = selection.get("episode")
        if season is not None and episode is not None:
            parts.append(f"S{season}E{episode}")
        parts.extend(
            [
                str(selection.get("language") or "Unknown"),
                str(selection.get("quality") or "Available"),
            ]
        )
        return " · ".join(parts)

    def _job_keyboard(self, job: MovieJob) -> InlineKeyboardMarkup:
        rows = []
        if job.state == "downloading":
            rows.append(
                [
                    InlineKeyboardButton(
                        "📥 Download Status", callback_data=f"movie:status:{job.job_id}"
                    ),
                    InlineKeyboardButton(
                        "Cancel", callback_data=f"movie:cancel:{job.job_id}"
                    ),
                ]
            )
        elif job.state == "choice":
            rows.append(
                [
                    InlineKeyboardButton(
                        "Queue", callback_data=f"movie:queue:{job.job_id}"
                    ),
                    InlineKeyboardButton(
                        "Replace…", callback_data=f"movie:replace:{job.job_id}"
                    ),
                    InlineKeyboardButton(
                        "Cancel", callback_data=f"movie:cancel:{job.job_id}"
                    ),
                ]
            )
        elif job.state == "awaiting_voice":
            rows.append(
                [
                    InlineKeyboardButton(
                        "🔄 Retry", callback_data=f"movie:retry:{job.job_id}"
                    ),
                    InlineKeyboardButton(
                        "⬅️ Back to Results", callback_data=f"movie:back:{job.job_id}"
                    ),
                ]
            )
        elif job.state == "failed":
            controls = []
            if job.retryable or (job.song is not None and job.path):
                controls.append(
                    InlineKeyboardButton(
                        "🔄 Retry", callback_data=f"movie:retry:{job.job_id}"
                    )
                )
            controls.append(
                InlineKeyboardButton(
                    "⬅️ Back to Results", callback_data=f"movie:back:{job.job_id}"
                )
            )
            rows.append(controls)
        elif job.state in {"playing", "queued", "completed"}:
            rows.append(
                [
                    InlineKeyboardButton(
                        "▶️ Now Playing", callback_data=f"movie:now:{job.job_id}"
                    ),
                    InlineKeyboardButton(
                        "⬅️ Back to Results", callback_data=f"movie:back:{job.job_id}"
                    ),
                ]
            )
        else:
            rows.append(
                [
                    InlineKeyboardButton(
                        "⬅️ Back to Results", callback_data=f"movie:back:{job.job_id}"
                    )
                ]
            )
        if job.state == "choice":
            rows.append(
                [
                    InlineKeyboardButton(
                        "⬅️ Back to Results", callback_data=f"movie:back:{job.job_id}"
                    )
                ]
            )
        return InlineKeyboardMarkup(rows)

    def _job_text(self, job: MovieJob) -> str:
        title = html.escape(self._selection_label(job.selection))
        prefix = f"🎬 <b>{title}</b>\n"
        if job.state == "downloading":
            if job.total_bytes:
                percent = min(100.0, job.bytes_downloaded * 100 / job.total_bytes)
                progress = f"{percent:.1f}% · {self._bytes(job.bytes_downloaded)} / {self._bytes(job.total_bytes)}"
            else:
                progress = f"{self._bytes(job.bytes_downloaded)} downloaded · total size unknown"
            speed = f"{self._bytes(job.speed)}/s" if job.speed > 0 else "calculating"
            eta = self._duration(job.eta) if job.eta is not None else "unknown"
            return (
                prefix
                + "⬇️ <b>Downloading in the background</b>\n"
                + f"Progress: {progress}\nSpeed: {speed}\nETA: {eta}"
            )
        if job.state == "choice":
            return (
                prefix
                + "✅ <b>Download ready.</b> Another stream is active.\n"
                + "Queue this episode, or replace the current stream (admin confirmation required)."
            )
        if job.state == "awaiting_voice":
            return (
                prefix
                + "✅ <b>Download ready.</b> Start a voice chat in this group, then tap Retry."
            )
        if job.state == "failed":
            return (
                prefix
                + "❌ "
                + html.escape(
                    job.failure_message
                    or "The download or stream could not be completed."
                )
            )
        if job.state == "queued":
            position = f" (position {job.queue_position})" if job.queue_position else ""
            return prefix + f"✅ Added to the voice-chat queue{position}."
        if job.state == "playing":
            return prefix + "▶️ <b>Streaming in the voice chat.</b>"
        if job.state == "completed":
            return (
                prefix
                + "✅ Playback finished. The cached file may be reused until it expires."
            )
        if job.state == "cancelled":
            return (
                prefix
                + "Cancelled. The original episode buttons remain available above."
            )
        return prefix + "Processing…"

    async def _update(self, job: MovieJob) -> None:
        try:
            await job.status_message.edit_text(
                self._job_text(job),
                parse_mode=enums.ParseMode.HTML,
                reply_markup=self._job_keyboard(job),
                disable_web_page_preview=True,
            )
        except Exception:
            logger.debug(
                "Could not update movie status message for job %s",
                job.job_id,
                exc_info=True,
            )

    def _chat_lock(self, chat_id: int) -> asyncio.Lock:
        return self.chat_locks.setdefault(chat_id, asyncio.Lock())

    def _pinned_paths(self) -> set:
        cache_dir = os.path.realpath(self.downloader.directory)
        protected = set()

        def pin_path(path):
            if not isinstance(path, str) or not os.path.isfile(path):
                return
            resolved = os.path.realpath(path)
            try:
                if os.path.commonpath((cache_dir, resolved)) == cache_dir:
                    protected.add(resolved)
            except ValueError:
                return

        def pin_song(song):
            path = getattr(song, "remote", None) if song else None
            pin_path(path)

        for chat_id in list(all_groups()):
            group = get_group(chat_id)
            pin_song(group.get("now_playing"))
            queue = get_queue(chat_id)
            for song in list(queue._queue):
                pin_song(song)
        for job in self.jobs.values():
            if job.path and job.state in {
                "downloading",
                "choice",
                "awaiting_voice",
                "failed",
            }:
                pin_path(job.path)
        return protected

    def _prune_jobs(self) -> None:
        cutoff = time.time() - 24 * 60 * 60
        for job_id, job in list(self.jobs.items()):
            if job.state != "downloading" and job.created_at < cutoff:
                self.jobs.pop(job_id, None)
        if len(self.jobs) > 500:
            inactive = sorted(
                (job for job in self.jobs.values() if job.state != "downloading"),
                key=lambda job: job.created_at,
            )
            for job in inactive[: max(0, len(self.jobs) - 500)]:
                self.jobs.pop(job.job_id, None)

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(60 * 60)
            try:
                await self.downloader.cleanup(self._pinned_paths())
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Movie cache cleanup failed")

    async def _new_job(self, callback: CallbackQuery, selection: Dict) -> MovieJob:
        self._prune_jobs()
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(
                self._cleanup_loop(), name="movie-cache-cleanup"
            )
        job_id = secrets.token_hex(5)
        result_message = callback.message
        initial = await result_message.reply_text(
            f"⬇️ Preparing <b>{html.escape(self._selection_label(selection))}</b>…",
            parse_mode=enums.ParseMode.HTML,
        )
        job = MovieJob(
            job_id=job_id,
            chat_id=result_message.chat.id,
            requester_id=callback.from_user.id,
            requester=callback.from_user,
            selection=selection,
            result_message=result_message,
            status_message=initial,
        )
        self.jobs[job_id] = job
        job.task = asyncio.create_task(
            self._run_download(job), name=f"movie-download-{job_id}"
        )
        await self._update(job)
        return job

    async def _run_download(self, job: MovieJob) -> None:
        last_progress_edit = 0.0

        async def on_progress(downloaded, total, speed, eta):
            nonlocal last_progress_edit
            job.bytes_downloaded = downloaded
            job.total_bytes = total
            job.speed = speed
            job.eta = eta
            now = time.monotonic()
            if now - last_progress_edit >= 3:
                last_progress_edit = now
                await self._update(job)

        try:
            job.path = await self.downloader.download(
                job.selection["url"],
                progress=on_progress,
                protected_paths=self._pinned_paths(),
            )
            episode = job.selection.get("episode")
            season = job.selection.get("season")
            display_title = str(job.selection.get("title") or "Untitled")
            if season is not None and episode is not None:
                display_title += f" S{season}E{episode}"
            display_title += f" · {job.selection.get('language') or 'Unknown'} · {job.selection.get('quality') or 'Available'}"
            song = Song(
                {
                    "title": Song._escape(display_title[:240]),
                    "source": job.selection["url"],
                    "remote": job.path,
                    "duration": str(job.selection.get("duration") or "N/A"),
                    "thumb": "https://telegra.ph/file/820cac7cb7b1a025542e2.jpg",
                    "headers": None,
                    "parsed": True,
                    "stream_mode": "video",
                    "movie_quality": str(job.selection.get("quality") or ""),
                    "movie_job_id": job.job_id,
                },
                job.result_message,
            )
            song.requested_by = job.requester
            job.song = song
            async with self._chat_lock(job.chat_id):
                group = get_group(job.chat_id)
                if group.get("is_playing"):
                    job.state = "choice"
                    await self._update(job)
                else:
                    await self._start_locked(job)
        except asyncio.CancelledError:
            job.state = "cancelled"
            await self._update(job)
            raise
        except MovieDownloadError as exc:
            job.state = "failed"
            job.retryable = exc.retryable
            job.failure_message = str(exc)
            await self._update(job)
        except Exception:
            logger.exception("Movie download job %s failed", job.job_id)
            job.state = "failed"
            job.retryable = True
            job.failure_message = (
                "A temporary server error occurred. Check the Railway log and Retry."
            )
            await self._update(job)

    async def _start_locked(self, job: MovieJob, *, replace: bool = False) -> None:
        group = get_group(job.chat_id)
        if group.get("is_playing") and not replace:
            job.state = "choice"
            await self._update(job)
            return
        previous_song = group.get("now_playing")
        previous_is_playing = group.get("is_playing", False)
        set_group(job.chat_id, is_playing=True, now_playing=job.song)
        try:
            await start_stream(
                job.song,
                load(group.get("lang") or config.LANGUAGE),
                create_if_missing=False,
            )
        except (NoActiveGroupCall, NotInCallError):
            set_group(
                job.chat_id,
                is_playing=previous_is_playing,
                now_playing=previous_song,
            )
            job.state = "awaiting_voice"
            await self._update(job)
        except Exception:
            logger.exception("Could not start movie stream for job %s", job.job_id)
            set_group(
                job.chat_id,
                is_playing=previous_is_playing,
                now_playing=previous_song,
            )
            job.state = "failed"
            job.retryable = True
            job.failure_message = "The download finished, but voice-chat playback failed. Check the Railway log and Retry."
            await self._update(job)
        else:
            if previous_song is not None and previous_song is not job.song:
                await self.mark_stream_finished(previous_song)
            job.state = "playing"
            job.retryable = False
            await self._update(job)

    async def mark_stream_started(self, song: Optional[Song]) -> None:
        job_id = getattr(song, "movie_job_id", None) if song else None
        job = self.jobs.get(job_id)
        if job:
            job.state = "playing"
            job.retryable = False
            await self._update(job)

    async def mark_stream_finished(self, song: Optional[Song]) -> None:
        job_id = getattr(song, "movie_job_id", None) if song else None
        job = self.jobs.get(job_id)
        if job and job.state in {"playing", "queued"}:
            job.state = "completed"
            await self._update(job)

    async def mark_queue_cleared(self, songs) -> None:
        for song in songs:
            job_id = getattr(song, "movie_job_id", None) if song else None
            job = self.jobs.get(job_id)
            if job and job.state == "queued":
                job.state = "cancelled"
                await self._update(job)

    async def _is_admin(self, chat_id: int, user_id: int) -> bool:
        if user_id in config.SUDOERS:
            return True
        try:
            member = await self.client.get_chat_member(chat_id, user_id)
            status = getattr(member, "status", "")
            status_text = " ".join(
                str(value)
                for value in (
                    getattr(status, "name", ""),
                    getattr(status, "value", ""),
                    status,
                )
            ).lower()
            return any(
                role in status_text for role in ("administrator", "owner", "creator")
            )
        except Exception:
            return False

    async def _can_control_job(self, callback: CallbackQuery, job: MovieJob) -> bool:
        user_id = getattr(callback.from_user, "id", None)
        return user_id == job.requester_id or await self._is_admin(job.chat_id, user_id)

    @staticmethod
    def _job_status_summary(job: MovieJob) -> str:
        if job.state == "downloading":
            if job.total_bytes:
                percent = min(100, int(job.bytes_downloaded * 100 / job.total_bytes))
                return f"Downloading: {percent}% · {MovieFeature._bytes(job.bytes_downloaded)} / {MovieFeature._bytes(job.total_bytes)}"
            return f"Downloading: {MovieFeature._bytes(job.bytes_downloaded)} received; total size unknown"
        return job.state.replace("_", " ").title()

    async def _handle_job_callback(
        self, callback: CallbackQuery, action: str, job_id: str
    ):
        job = self.jobs.get(job_id)
        if not job or job.chat_id != callback.message.chat.id:
            await callback.answer(
                "This movie action expired. Search again.", show_alert=True
            )
            return

        if action == "status":
            await callback.answer(self._job_status_summary(job), show_alert=True)
            return
        if action == "now":
            current = get_group(job.chat_id).get("now_playing")
            if current:
                await callback.answer(
                    f"Now playing: {getattr(current, 'title', 'Media')[:180]}",
                    show_alert=True,
                )
            else:
                await callback.answer("Nothing is currently playing.", show_alert=True)
            return
        if action == "back":
            await callback.answer(
                "The original results and episode buttons remain available above.",
                show_alert=True,
            )
            return
        if action in {"cancel", "retry"} and not await self._can_control_job(
            callback, job
        ):
            await callback.answer(
                "Only the requester or a group admin can control this download.",
                show_alert=True,
            )
            return

        if action == "cancel":
            if job.state == "downloading" and job.task and not job.task.done():
                job.task.cancel()
                await callback.answer("Cancelling the download…")
                return
            if job.state == "queued":
                async with self._chat_lock(job.chat_id):
                    queue = get_queue(job.chat_id)
                    try:
                        queue._queue.remove(job.song)
                    except ValueError:
                        await callback.answer(
                            "This item is already playing or no longer queued.",
                            show_alert=True,
                        )
                        return
            elif job.state not in {"choice", "awaiting_voice", "failed"}:
                await callback.answer(
                    "This item can no longer be cancelled here.", show_alert=True
                )
                return
            job.state = "cancelled"
            await self._update(job)
            await callback.answer("Selection cancelled.")
            return

        if action == "retry":
            if job.song and job.path:
                async with self._chat_lock(job.chat_id):
                    await self._start_locked(job)
                await callback.answer("Retrying voice-chat playback.")
            elif job.state == "failed" and job.retryable:
                job.state = "downloading"
                job.bytes_downloaded = 0
                job.total_bytes = None
                job.speed = 0.0
                job.eta = None
                job.failure_message = ""
                job.retryable = False
                job.task = asyncio.create_task(
                    self._run_download(job), name=f"movie-download-{job.job_id}-retry"
                )
                await self._update(job)
                await callback.answer("Retrying the download.")
            else:
                await callback.answer(
                    "This item cannot be retried; search again for a fresh link.",
                    show_alert=True,
                )
            return

        if action == "queue":
            if job.state != "choice" or not job.song:
                await callback.answer(
                    "This download is not ready to queue.", show_alert=True
                )
                return
            async with self._chat_lock(job.chat_id):
                group = get_group(job.chat_id)
                if group.get("is_playing"):
                    queue = get_queue(job.chat_id)
                    await queue.put(job.song)
                    job.queue_position = len(queue)
                    job.state = "queued"
                    await self._update(job)
                else:
                    await self._start_locked(job)
            await callback.answer("Added to the queue or started playback.")
            return

        if action == "replace":
            if job.state != "choice" or not job.song:
                await callback.answer(
                    "This download is not ready to replace the stream.", show_alert=True
                )
                return
            if not await self._is_admin(job.chat_id, callback.from_user.id):
                await callback.answer(
                    "Replacing the current stream is admin-only.", show_alert=True
                )
                return
            await job.status_message.reply_text(
                f"Replace the current stream with <b>{html.escape(self._selection_label(job.selection))}</b>?",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Confirm replace",
                                callback_data=f"movie:replace_confirm:{job.job_id}",
                            ),
                            InlineKeyboardButton(
                                "Cancel", callback_data=f"movie:cancel:{job.job_id}"
                            ),
                        ]
                    ]
                ),
            )
            await callback.answer("Confirm the replacement in the message below.")
            return

        if action == "replace_confirm":
            if not await self._is_admin(job.chat_id, callback.from_user.id):
                await callback.answer(
                    "Replacing the current stream is admin-only.", show_alert=True
                )
                return
            if job.state != "choice" or not job.song:
                await callback.answer(
                    "This movie is no longer waiting to replace the stream.",
                    show_alert=True,
                )
                return
            async with self._chat_lock(job.chat_id):
                await self._start_locked(job, replace=True)
            await callback.answer("Replacement requested.")
            return

        await callback.answer("Unsupported movie action.", show_alert=True)

    async def handle_callback(self, _, callback: CallbackQuery) -> None:
        if not callback.message or not callback.message.chat:
            await callback.answer("This action is unavailable here.", show_alert=True)
            return
        try:
            parts = (callback.data or "").split(":")
            if len(parts) < 3 or parts[0] != "movie":
                await callback.answer("Invalid movie action.", show_alert=True)
                return
            action = parts[1]
            chat_id = callback.message.chat.id

            if action == "page" and len(parts) == 4:
                session_id = parts[2]
                if not get_movie_session(session_id, chat_id):
                    await callback.answer(
                        "These results expired. Search again.", show_alert=True
                    )
                    return
                try:
                    page = int(parts[3])
                except ValueError:
                    await callback.answer("Invalid results page.", show_alert=True)
                    return
                set_movie_page(session_id, page)
                await callback.message.edit_reply_markup(
                    create_movie_keyboard(session_id)
                )
                await callback.answer()
                return

            if action in {"language", "quality", "reset"} and len(parts) == 3:
                session_id = parts[2]
                if not get_movie_session(session_id, chat_id):
                    await callback.answer(
                        "These results expired. Search again.", show_alert=True
                    )
                    return
                if action == "reset":
                    reset_movie_filters(session_id)
                else:
                    cycle_movie_filter(session_id, action)
                await callback.message.edit_reply_markup(
                    create_movie_keyboard(session_id)
                )
                await callback.answer()
                return

            if action == "select" and len(parts) == 4:
                session_id = parts[2]
                try:
                    index = int(parts[3])
                except ValueError:
                    await callback.answer("Invalid episode selection.", show_alert=True)
                    return
                selection = get_movie_selection(session_id, index, chat_id)
                if not selection:
                    await callback.answer(
                        "This episode choice expired. Search again.", show_alert=True
                    )
                    return
                await callback.answer("Background download started.")
                await self._new_job(callback, selection)
                return

            if len(parts) == 3:
                await self._handle_job_callback(callback, action, parts[2])
                return

            await callback.answer("Invalid movie action.", show_alert=True)
        except Exception:
            logger.exception("Movie callback failed")
            try:
                await callback.answer(
                    "A movie action failed. Check the Railway log and try again.",
                    show_alert=True,
                )
            except Exception:
                pass
