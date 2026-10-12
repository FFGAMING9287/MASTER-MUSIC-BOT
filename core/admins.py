"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

from config import config
from pyrogram.types import Message

async def is_admin(message: Message):
    if message.from_user.id in config.SUDO_USERS:
        return True
    # more logic from original
    return False

async def is_sudo(message: Message):
    return message.from_user.id in config.SUDO_USERS
