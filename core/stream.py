"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

import os
from config import config
from pyrogram import Client
from yt_dlp import YoutubeDL

# Compatible import for different pytgcalls versions
PyTgCalls = None
MediaStream = None
AudioQuality = None
VideoQuality = None

try:
    from pytgcalls import PyTgCalls
except ImportError:
    try:
        from pytgcalls.pytgcalls import PyTgCalls
    except ImportError:
        PyTgCalls = None

try:
    from pytgcalls.types.stream import MediaStream
except ImportError:
    try:
        from pytgcalls.types import MediaStream
    except ImportError:
        MediaStream = None

try:
    from pytgcalls.types import AudioQuality, VideoQuality
except ImportError:
    AudioQuality = None
    VideoQuality = None

ydl_opts = {
    "quiet": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
}

app = Client(
    "MusicPlayerUB",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=getattr(config, "SESSION", None) or "",
    in_memory=True,
)

ytdl = YoutubeDL(ydl_opts)

pytgcalls = None
if PyTgCalls is not None:
    try:
        pytgcalls = PyTgCalls(app)
    except Exception as e:
        print(f"PyTgCalls init warning: {e}")

async def start_stream(song, lang=None):
    """Placeholder - full stream logic to be restored."""
    pass
