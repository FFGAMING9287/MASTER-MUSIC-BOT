"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class Song:
    title: str
    duration: int
    url: str
    thumb: Optional[str] = None
    requester: Optional[str] = None

    def __str__(self):
        return f"{self.title} ({self.duration}s)"
