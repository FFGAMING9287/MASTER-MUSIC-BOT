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
from core.song import Song
from pyrogram.types import Message
from pyrogram import Client, filters
from core.decorators import language, register, only_admins, handle_error
from core import (
    app, ytdl, safone, search, is_sudo, is_admin, get_group, get_queue,
    pytgcalls, set_group, set_title, all_groups, clear_queue, check_yt_url,
    extract_args, start_stream, shuffle_queue, delete_messages,
    get_spotify_playlist, get_youtube_playlist)

# Safe imports for pytgcalls (version differences)
try:
    from pytgcalls.types import Update, ChatUpdate
except ImportError:
    Update = object
    ChatUpdate = object

try:
    from pytgcalls.types.stream import StreamEnded
except ImportError:
    StreamEnded = type("StreamEnded", (), {})

try:
    from pytgcalls.exceptions import NotInCallError, NoActiveGroupCall
except ImportError:
    class NotInCallError(Exception): pass
    class NoActiveGroupCall(Exception): pass


REPO = """
🤖 **Music Player**

- Repo: [GitHub](https://github.com/FFGAMING9287/MUSICBOT.git)
- License: AGPL-3.0-or-later
"""

if config.BOT_TOKEN:
    bot = Client(
        "MusicPlayer",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    )
    client = bot
else:
    client = app


@client.on_message(filters.command("repo", config.PREFIXES) & ~filters.bot)
@handle_error
async def repo(_, message: Message):
    await message.reply_text(REPO, disable_web_page_preview=True)


@client.on_message(filters.command("ping", config.PREFIXES) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await message.reply_text("🤖 **Pong!**")


@client.on_message(filters.command("start", config.PREFIXES) & ~filters.bot)
@language
@handle_error
async def start(_, message: Message, lang):
    await message.reply_text(lang.get("startText", "Hello {0}") % message.from_user.mention)


@client.on_message(filters.command("help", config.PREFIXES) & ~filters.bot)
@language
@handle_error
async def help(_, message: Message, lang):
    await message.reply_text(lang.get("helpText", "Help").replace("<prefix>", config.PREFIXES[0]))


@client.on_message(filters.command(["p", "play"], config.PREFIXES) & ~filters.private)
@register
@language
@handle_error
async def play_stream(_, message: Message, lang):
    chat_id = message.chat.id
    group = get_group(chat_id)
    if group.get("admins_only"):
        check = await is_admin(message)
        if not check:
            k = await message.reply_text(lang.get("notAllowed", "Not allowed"))
            return await delete_messages([message, k])
    song = await search(message)
    if song is None:
        k = await message.reply_text(lang.get("notFound", "Not found"))
        return await delete_messages([message, k])
    ok, status = await song.parse()
    if not ok:
        raise Exception(status)
    if not group.get("is_playing"):
        set_group(chat_id, is_playing=True, now_playing=song)
        await start_stream(song, lang)
        await delete_messages([message])
    else:
        queue = get_queue(chat_id)
        await queue.put(song)
        k = await message.reply_text(
            lang.get("addedToQueue", "Added to queue") % (song.title, song.source, len(queue)),
            disable_web_page_preview=True,
        )
        await delete_messages([message, k])


print("Music Player main loaded successfully")
