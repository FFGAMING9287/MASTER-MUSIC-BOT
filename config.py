"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

from os import getenv
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(getenv("API_ID", "0"))
    API_HASH = getenv("API_HASH", "")
    BOT_TOKEN = getenv("BOT_TOKEN", "")
    SESSION = getenv("SESSION", "")
    PREFIXES = list(getenv("PREFIXES", "! . /").split())
    SUDO_USERS = list(map(int, getenv("SUDO_USERS", "").split())) if getenv("SUDO_USERS") else []
    DURATION_LIMIT = int(getenv("DURATION_LIMIT", "60"))
    # ... more from original, simplified for this push

config = Config()
