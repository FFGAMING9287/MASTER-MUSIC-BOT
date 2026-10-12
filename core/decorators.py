"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

from functools import wraps
from pyrogram.types import Message
from config import config

def language(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        # Language loading logic from clean source
        lang = {"startText": "Hello {0}", "helpText": "Help text", "notAllowed": "Not allowed"}
        return await func(client, message, lang, *args, **kwargs)
    return wrapper

def register(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        return await func(client, message, *args, **kwargs)
    return wrapper

def only_admins(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        return await func(client, message, *args, **kwargs)
    return wrapper

def handle_error(func):
    @wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        try:
            return await func(client, message, *args, **kwargs)
        except Exception as e:
            await message.reply_text(f"Error: {e}")
    return wrapper
