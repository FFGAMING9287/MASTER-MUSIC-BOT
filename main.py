"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ /* ᴍᴜꜱɪᴄ ʙᴏᴛ !!

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from config import Config
from core import (
    admins,
    decorators,
    funcs,
    groups,
    queue,
    song,
    stream,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOGGER = logging.getLogger(__name__)

app = Client(
    "MusicPlayer",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
)

# NOTE: This is a partial restore. Full clean main.py from zip will be completed in next commits.
print("Clean MusicPlayer main loaded")
