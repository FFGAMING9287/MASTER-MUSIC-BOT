"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

import os
from config import config
from pyrogram import Client
from yt_dlp import YoutubeDL

try:
    from pytgcalls import PyTgCalls
except ImportError:
    from py_tgcalls import PyTgCalls

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
    session_string=getattr(config, "SESSION", ""),
    in_memory=True,
)

ytdl = YoutubeDL(ydl_opts)
pytgcalls = PyTgCalls(app)

async def start_stream(song, lang=None):
    """Basic start stream placeholder - full logic to be restored."""
    pass
