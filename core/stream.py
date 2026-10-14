"""
Stream helper - play / pause / resume / skip / stop / queue
"""

import os
from config import config
from pyrogram import Client
from yt_dlp import YoutubeDL
from pytgcalls import PyTgCalls
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
    """Try every known method to leave / stop the stream."""
    await _ensure_started()
    methods = [
        "leave_group_call",
        "leave_call",
        "stop",
        "hangup",
    ]
    for name in methods:
        try:
            fn = getattr(pytgcalls, name, None)
            if fn:
                await fn(chat_id)
                return True
        except Exception:
            continue
    # Last resort: play nothing / empty
    try:
        await pytgcalls.play(chat_id, None)
    except Exception:
        pass
    return False

async def play_local_file(chat_id: int, file_path: str, title: str = "Video", force=False):
    if not os.path.exists(file_path):
        return False, "File not found"

    state = get_state(chat_id)

    if state["playing"] and not force:
        state["queue"].append({"path": file_path, "title": title})
        pos = len(state["queue"])
        return True, f"Added to queue at position **#{pos}**\n**{title}**"

    try:
        await _ensure_started()
        stream = MediaStream(
            file_path,
            AudioQuality.HIGH,
            VideoQuality.SD_480p,
        )
        await pytgcalls.play(chat_id, stream)
        state["playing"] = True
        state["paused"] = False
        state["title"] = title
        state["path"] = file_path
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
            stream = MediaStream(
                file_path,
                AudioQuality.HIGH,
                VideoQuality.SD_480p,
            )
            await pytgcalls.play(chat_id, stream)
            state["playing"] = True
            state["paused"] = False
            state["title"] = title
            state["path"] = file_path
            return True, f"Created VC + now playing **{title}**"
        except Exception as e2:
            return False, f"No active Voice Chat and could not create one: {e2}"
    except Exception as e:
        err = str(e).lower()
        if "session" in err or "auth" in err:
            return False, "SESSION invalid or missing"
        return False, f"Play error: {str(e)[:180]}"

async def pause_stream(chat_id: int):
    state = get_state(chat_id)
    if not state["playing"]:
        return False, "Nothing is playing"
    if state["paused"]:
        return False, "Already paused"
    try:
        await _ensure_started()
        try:
            await pytgcalls.pause_stream(chat_id)
        except Exception:
            await pytgcalls.pause(chat_id)
        state["paused"] = True
        return True, f"⏸ Paused: **{state['title']}**"
    except Exception as e:
        return False, f"Pause failed: {str(e)[:120]}"

async def resume_stream(chat_id: int):
    state = get_state(chat_id)
    if not state["playing"]:
        return False, "Nothing is playing"
    if not state["paused"]:
        return False, "Not paused"
    try:
        await _ensure_started()
        try:
            await pytgcalls.resume_stream(chat_id)
        except Exception:
            await pytgcalls.resume(chat_id)
        state["paused"] = False
        return True, f"▶️ Resumed: **{state['title']}**"
    except Exception as e:
        return False, f"Resume failed: {str(e)[:120]}"

async def skip_stream(chat_id: int):
    state = get_state(chat_id)
    if not state["playing"] and not state["queue"]:
        return False, "Nothing is playing and queue is empty"

    await _leave_call(chat_id)

    state["playing"] = False
    state["paused"] = False
    state["title"] = None
    state["path"] = None

    if state["queue"]:
        next_item = state["queue"].pop(0)
        ok, msg = await play_local_file(chat_id, next_item["path"], next_item["title"], force=True)
        if ok:
            return True, f"⏭ Skipped\n{msg}\nQueue left: {len(state['queue'])}"
        return False, f"Skipped but next failed: {msg}"

    return True, "⏭ Skipped. Queue empty."

async def stop_stream(chat_id: int):
    """Fully stop streaming and clear queue."""
    state = get_state(chat_id)
    was_playing = state["playing"] or bool(state["queue"])

    await _leave_call(chat_id)

    state["playing"] = False
    state["paused"] = False
    state["title"] = None
    state["path"] = None
    state["queue"] = []

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
