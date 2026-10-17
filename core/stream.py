"""
Stream helper - play / pause / resume / skip / stop / queue / seek
Audio-focused MediaStream for reliable VC sound.
"""

import os
import time
import asyncio
from config import config
from pyrogram import Client
from yt_dlp import YoutubeDL
from pytgcalls import PyTgCalls
from pytgcalls import filters as fl
from pytgcalls.types.stream import MediaStream
from pytgcalls.types import AudioQuality, VideoQuality
from pytgcalls.exceptions import NoActiveGroupCall
from pyrogram.raw.types import InputPeerChannel
from pyrogram.raw.functions.phone import CreateGroupCall

ydl_opts = {
    "quiet": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
}

app = Client(
    "MusicPlayerUB",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=getattr(config, "SESSION", "") or "",
    in_memory=True,
)
ytdl = YoutubeDL(ydl_opts)
pytgcalls = PyTgCalls(app)

_started = False
chat_state = {}


def get_state(chat_id):
    if chat_id not in chat_state:
        chat_state[chat_id] = {
            "playing": False,
            "paused": False,
            "title": None,
            "path": None,
            "queue": [],
            "duration": 0,
            "seek_offset": 0,
        }
    return chat_state[chat_id]


async def _ensure_started():
    global _started
    if not _started:
        if not app.is_connected:
            await app.start()
        await pytgcalls.start()
        _started = True
        print("PyTgCalls + userbot started")


async def _leave_call(chat_id: int):
    await _ensure_started()
    for name in ("leave_group_call", "leave_call", "stop", "hangup"):
        try:
            fn = getattr(pytgcalls, name, None)
            if fn:
                await fn(chat_id)
                return True
        except Exception:
            continue
    try:
        await pytgcalls.play(chat_id, None)
    except Exception:
        pass
    return False


async def _play_next_or_leave(chat_id: int):
    state = get_state(chat_id)
    state["playing"] = False
    state["paused"] = False
    state["title"] = None
    state["path"] = None
    state["seek_offset"] = 0

    if state["queue"]:
        next_item = state["queue"].pop(0)
        is_remote = next_item.get("remote", False)
        title = next_item.get("title", "Next")
        try:
            if is_remote:
                ok, msg = await play_remote_url(chat_id, next_item["path"], title, force=True)
            else:
                ok, msg = await play_local_file(chat_id, next_item["path"], title, force=True)
            if ok:
                try:
                    await app.send_message(
                        chat_id,
                        f"⏭ **Auto-playing next**\n🎵 **{title}**\nQueue left: {len(state['queue'])}",
                    )
                except Exception:
                    pass
                return
            await _play_next_or_leave(chat_id)
            return
        except Exception as e:
            print(f"Auto next error: {e}")

    await _leave_call(chat_id)
    try:
        await app.send_message(
            chat_id,
            "⏹ **Queue finished**\nNothing left to play. Bot left the Voice Chat.",
        )
    except Exception:
        pass


try:

    @pytgcalls.on_update(fl.stream_end())
    async def _on_stream_end(_, update):
        chat_id = getattr(update, "chat_id", None)
        if chat_id is None:
            return
        print(f"Stream ended in {chat_id}")
        await _play_next_or_leave(chat_id)

except Exception as e:
    print(f"stream_end register fail: {e}")
    try:

        @pytgcalls.on_stream_end()
        async def _on_stream_end_old(_, update):
            chat_id = getattr(update, "chat_id", None)
            if chat_id is None:
                return
            await _play_next_or_leave(chat_id)

    except Exception as e2:
        print(f"No stream_end: {e2}")


async def _do_play(chat_id, stream):
    await pytgcalls.play(chat_id, stream)


def _audio_stream(path_or_url: str, with_video: bool = False):
    """Build MediaStream preferring audio so VC has sound."""
    if with_video and os.path.isfile(str(path_or_url)):
        try:
            return MediaStream(path_or_url, AudioQuality.HIGH, VideoQuality.SD_480p)
        except Exception:
            pass
    # Audio-only path (most reliable for music)
    try:
        return MediaStream(
            path_or_url,
            AudioQuality.HIGH,
            video_flags=MediaStream.Flags.IGNORE,
        )
    except Exception:
        try:
            return MediaStream(path_or_url, AudioQuality.HIGH)
        except Exception:
            return MediaStream(path_or_url)


async def play_local_file(chat_id: int, file_path: str, title: str = "Video", force=False, start_sec: int = 0):
    if not os.path.exists(file_path):
        return False, "File not found"

    state = get_state(chat_id)

    if state["playing"] and not force:
        state["queue"].append({"path": file_path, "title": title, "remote": False})
        return True, f"Added to queue at position **#{len(state['queue'])}**\n**{title}**"

    play_path = file_path
    if start_sec and start_sec > 0:
        tmp = f"/tmp/seek_{chat_id}_{int(time.time())}.mp4"
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-ss", str(int(start_sec)), "-i", file_path,
                "-c", "copy", "-avoid_negative_ts", "1", tmp,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=60)
            if proc.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
                play_path = tmp
        except Exception as e:
            print(f"ffmpeg seek error: {e}")

    # Music files → audio only; video files → with video
    is_audio_ext = str(play_path).lower().endswith((".m4a", ".mp3", ".webm", ".ogg", ".opus", ".flac", ".wav"))
    try:
        await _ensure_started()
        stream = _audio_stream(play_path, with_video=not is_audio_ext)
        await _do_play(chat_id, stream)
        state["playing"] = True
        state["paused"] = False
        state["title"] = title
        state["path"] = file_path
        state["seek_offset"] = int(start_sec or 0)
        return True, f"Now playing **{title}** in Voice Chat"
    except NoActiveGroupCall:
        try:
            peer = await app.resolve_peer(chat_id)
            await app.invoke(
                CreateGroupCall(
                    peer=InputPeerChannel(
                        channel_id=peer.channel_id,
                        access_hash=peer.access_hash,
                    ),
                    random_id=app.rnd_id() // 9000000000,
                )
            )
            stream = _audio_stream(play_path, with_video=not is_audio_ext)
            await _do_play(chat_id, stream)
            state["playing"] = True
            state["paused"] = False
            state["title"] = title
            state["path"] = file_path
            state["seek_offset"] = int(start_sec or 0)
            return True, f"Created VC + now playing **{title}**"
        except Exception as e2:
            return False, f"No active Voice Chat and could not create one: {e2}"
    except Exception as e:
        err = str(e).lower()
        if "session" in err or "auth" in err:
            return False, "SESSION invalid or missing"
        return False, f"Play error: {str(e)[:180]}"


async def play_remote_url(chat_id: int, stream_url: str, title: str = "YouTube", force=False):
    state = get_state(chat_id)

    if state["playing"] and not force:
        state["queue"].append({"path": stream_url, "title": title, "remote": True})
        return True, f"Added to queue at position **#{len(state['queue'])}**\n**{title}**"

    # If path is actually a local file, route to local player
    if os.path.isfile(str(stream_url)):
        return await play_local_file(chat_id, stream_url, title, force=force)

    try:
        await _ensure_started()
        stream = _audio_stream(stream_url, with_video=False)
        await _do_play(chat_id, stream)
        state["playing"] = True
        state["paused"] = False
        state["title"] = title
        state["path"] = stream_url
        state["seek_offset"] = 0
        return True, f"Now playing **{title}** in Voice Chat"
    except NoActiveGroupCall:
        try:
            peer = await app.resolve_peer(chat_id)
            await app.invoke(
                CreateGroupCall(
                    peer=InputPeerChannel(
                        channel_id=peer.channel_id,
                        access_hash=peer.access_hash,
                    ),
                    random_id=app.rnd_id() // 9000000000,
                )
            )
            stream = _audio_stream(stream_url, with_video=False)
            await _do_play(chat_id, stream)
            state["playing"] = True
            state["paused"] = False
            state["title"] = title
            state["path"] = stream_url
            return True, f"Created VC + now playing **{title}**"
        except Exception as e2:
            return False, f"No active Voice Chat: {e2}"
    except Exception as e:
        try:
            stream = MediaStream(stream_url, AudioQuality.HIGH)
            await _do_play(chat_id, stream)
            state["playing"] = True
            state["paused"] = False
            state["title"] = title
            state["path"] = stream_url
            return True, f"Now playing **{title}**"
        except Exception as e2:
            return False, f"Play error: {str(e2)[:180]}"


async def pause_stream(chat_id: int):
    state = get_state(chat_id)
    if not state.get("playing"):
        return False, "Nothing is playing"
    if state.get("paused"):
        return False, "Already paused"

    await _ensure_started()
    last_err = None
    for name in ("pause_stream", "pause", "pause_call", "mute_stream"):
        try:
            fn = getattr(pytgcalls, name, None)
            if not fn:
                continue
            await fn(chat_id)
            state["paused"] = True
            return True, f"⏸ Paused: **{state.get('title') or 'Track'}**"
        except Exception as e:
            last_err = e
            continue

    try:
        gc = getattr(pytgcalls, "group_calls", None) or getattr(pytgcalls, "_calls", None)
        if gc and chat_id in gc:
            call = gc[chat_id]
            for name in ("pause_stream", "pause", "mute"):
                fn = getattr(call, name, None)
                if fn:
                    await fn()
                    state["paused"] = True
                    return True, f"⏸ Paused: **{state.get('title') or 'Track'}**"
    except Exception as e:
        last_err = e

    return False, f"Pause failed: {str(last_err)[:120] if last_err else 'no method'}"


async def resume_stream(chat_id: int):
    state = get_state(chat_id)
    if not state.get("playing"):
        return False, "Nothing is playing"
    if not state.get("paused"):
        return True, "Already playing"

    await _ensure_started()
    last_err = None
    for name in ("resume_stream", "resume", "resume_call", "unmute_stream"):
        try:
            fn = getattr(pytgcalls, name, None)
            if not fn:
                continue
            await fn(chat_id)
            state["paused"] = False
            return True, f"▶️ Resumed: **{state.get('title') or 'Track'}**"
        except Exception as e:
            last_err = e
            continue

    try:
        gc = getattr(pytgcalls, "group_calls", None) or getattr(pytgcalls, "_calls", None)
        if gc and chat_id in gc:
            call = gc[chat_id]
            for name in ("resume_stream", "resume", "unmute"):
                fn = getattr(call, name, None)
                if fn:
                    await fn()
                    state["paused"] = False
                    return True, f"▶️ Resumed: **{state.get('title') or 'Track'}**"
    except Exception as e:
        last_err = e

    return False, f"Resume failed: {str(last_err)[:120] if last_err else 'no method'}"


async def seek_stream(chat_id: int, delta: int):
    state = get_state(chat_id)
    if not state.get("playing"):
        return False, "Nothing is playing"

    path = state.get("path")
    if not path or not os.path.isfile(str(path)):
        return False, "Seek only works on downloaded files"

    base = int(state.get("elapsed_base") or 0)
    if state.get("paused"):
        cur = base
    else:
        start = state.get("start_ts") or time.time()
        cur = base + int(time.time() - start)

    seek_off = int(state.get("seek_offset") or 0)
    absolute = max(0, seek_off + cur + int(delta))
    duration = int(state.get("duration") or 0)
    if duration and absolute >= duration - 2:
        absolute = max(0, duration - 2)

    title = state.get("title") or "Track"
    was_paused = state.get("paused")

    ok, msg = await play_local_file(chat_id, path, title, force=True, start_sec=absolute)
    if not ok:
        return False, msg

    state["elapsed_base"] = 0
    state["start_ts"] = time.time()
    state["seek_offset"] = absolute
    if was_paused:
        await pause_stream(chat_id)

    direction = "+" if delta > 0 else ""
    return True, f"Seek {direction}{delta}s → {absolute}s"


async def skip_stream(chat_id: int):
    state = get_state(chat_id)
    if not state["playing"] and not state["queue"]:
        return False, "Nothing is playing and queue is empty"

    await _leave_call(chat_id)
    state["playing"] = False
    state["paused"] = False
    state["title"] = None
    state["path"] = None
    state["seek_offset"] = 0

    if state["queue"]:
        next_item = state["queue"].pop(0)
        is_remote = next_item.get("remote", False)
        if is_remote:
            ok, msg = await play_remote_url(chat_id, next_item["path"], next_item["title"], force=True)
        else:
            ok, msg = await play_local_file(chat_id, next_item["path"], next_item["title"], force=True)
        if ok:
            return True, f"⏭ Skipped\n{msg}\nQueue left: {len(state['queue'])}"
        return False, f"Skipped but next failed: {msg}"

    return True, "⏭ Skipped. Queue empty."


async def stop_stream(chat_id: int):
    state = get_state(chat_id)
    was_playing = state["playing"] or bool(state["queue"])
    await _leave_call(chat_id)
    state["playing"] = False
    state["paused"] = False
    state["title"] = None
    state["path"] = None
    state["queue"] = []
    state["seek_offset"] = 0
    if was_playing:
        return True, "⏹ **Stopped streaming**\nQueue cleared. Bot left the Voice Chat."
    return True, "⏹ Nothing was playing. Queue cleared."


def get_queue_text(chat_id: int):
    state = get_state(chat_id)
    lines = []
    if state["playing"]:
        status = "⏸ Paused" if state["paused"] else "▶️ Playing"
        lines.append(f"{status}: **{state['title']}**")
    else:
        lines.append("Nothing playing.")
    if state["queue"]:
        lines.append(f"\n**Queue ({len(state['queue'])}):**")
        for i, item in enumerate(state["queue"][:15], 1):
            lines.append(f"{i}. {item['title']}")
        if len(state["queue"]) > 15:
            lines.append(f"... and {len(state['queue'])-15} more")
    else:
        lines.append("\nQueue is empty.")
    return "\n".join(lines)


async def start_stream(song, lang=None):
    pass
