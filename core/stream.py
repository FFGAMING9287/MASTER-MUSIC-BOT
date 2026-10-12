"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

import os
from config import config
from pyrogram import Client
from yt_dlp import YoutubeDL

# Compatible import for different pytgcalls versions
try:
    from pytgcalls import PyTgCalls
except ImportError:
    try:
        from pytgcalls.pytgcalls import PyTgCalls
    except ImportError:
        from pytgcalls import GroupCallFactory as PyTgCalls  # very old fallback

from pytgcalls.types.stream import MediaStream
from pytgcalls.types import AudioQuality, VideoQuality

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

try:
    pytgcalls = PyTgCalls(app)
except Exception as e:
    print(f"PyTgCalls init warning: {e}")
    pytgcalls = None

async def start_stream(song, lang=None):
    """Placeholder - full stream logic to be restored from clean source."""
    pass
