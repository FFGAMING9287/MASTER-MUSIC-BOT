"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

from pytgcalls import PyTgCalls
from config import config

pytgcalls = PyTgCalls(app) if 'app' in globals() else None

async def start_stream(chat_id, song):
    # Stream logic from clean zip
    pass
