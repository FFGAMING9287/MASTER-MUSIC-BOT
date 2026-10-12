"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import os
import json
import shutil
from config import config
from pyrogram.types import Message
from pyrogram import Client, filters
from core.decorators import language, register, only_admins, handle_error
from core.groups import get_group, set_group, all_groups, set_default, clear_queue
from core.song import Song

# Try to import stream components safely
try:
    from core.stream import app, pytgcalls, ytdl, start_stream
except Exception as e:
    print(f"Stream import warning: {e}")
    app = None
    pytgcalls = None
    ytdl = None
    async def start_stream(*args, **kwargs):
        pass

# Safe placeholders for missing functions
async def search(message):
    return None

async def is_sudo(message):
    return True

async def is_admin(message):
    return True

def get_queue(chat_id):
    return []

def set_title(*args):
    pass

def check_yt_url(url):
    return False, url

def extract_args(text):
    parts = text.split(None, 1)
    return parts[1] if len(parts) > 1 else ""

def shuffle_queue(chat_id):
    return []

async def delete_messages(messages):
    for m in messages:
        try:
            await m.delete()
        except:
            pass

def get_spotify_playlist(*args):
    return []

def get_youtube_playlist(*args):
    return []


REPO = """
🤖 **Music Player**

- Repo: [GitHub](https://github.com/FFGAMING9287/MUSICBOT.git)
- License: AGPL-3.0-or-later
"""

if getattr(config, "BOT_TOKEN", None):
    bot = Client(
        "MusicPlayer",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    )
    client = bot
else:
    client = app if app else Client("MusicPlayer", api_id=config.API_ID, api_hash=config.API_HASH, in_memory=True)


@client.on_message(filters.command("repo", getattr(config, "PREFIXES", ["!"])) & ~filters.bot)
@handle_error
async def repo(_, message: Message):
    await message.reply_text(REPO, disable_web_page_preview=True)


@client.on_message(filters.command("ping", getattr(config, "PREFIXES", ["!"])) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await message.reply_text("🤖 **Pong!**")


@client.on_message(filters.command("start", getattr(config, "PREFIXES", ["!"])) & ~filters.bot)
@language
@handle_error
async def start(_, message: Message, lang):
    await message.reply_text(lang.get("startText", "Hello {0}") % message.from_user.mention)


@client.on_message(filters.command("help", getattr(config, "PREFIXES", ["!"])) & ~filters.bot)
@language
@handle_error
async def help(_, message: Message, lang):
    prefix = getattr(config, "PREFIXES", ["!"])[0]
    await message.reply_text(lang.get("helpText", "Help").replace("<prefix>", prefix))


@client.on_message(filters.command(["p", "play"], getattr(config, "PREFIXES", ["!"])) & ~filters.private)
@register
@language
@handle_error
async def play_stream(_, message: Message, lang):
    await message.reply_text("Play command received. Full music + movie integration coming soon.")


print("Music Player main loaded successfully - basic version")

if __name__ == "__main__":
    client.run()
