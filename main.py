"""
Music Player — Yoru-style player UI with colored buttons (FFGAMING)
"""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import os
import time
from config import config
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters
from core.decorators import register, handle_error
from movie_api import search_movie, search_adult, download_file
from core.stream import (
    play_local_file,
    play_remote_url,
    pause_stream,
    resume_stream,
    skip_stream,
    stop_stream,
    seek_stream,
    get_queue_text,
    get_state,
)
from core.youtube import search_youtube, get_stream_info
from core.rich_ui import (
    send_rich,
    html_start,
    html_help,
    html_now_playing,
    html_search,
    html_download,
    html_queue,
    html_ping,
    html_mode,
    html_error,
    html_info,
    plain_now_playing,
    clean_name,
    status_searching,
    status_downloading,
    status_results,
)
from core.duration import duration_from_file, duration_from_item
from core.progress import start_progress, cancel_progress, on_pause, on_resume
from core.buttons import player_keyboard_api, send_message_styled, edit_message_styled

movie_cache = {}
adult_cache = {}
yt_cache = {}
BOT_PUBLIC = True

def extract_args(text):
    parts = text.split(None, 1)
    return parts[1] if len(parts) > 1 else ""

def is_owner(user_id: int) -> bool:
    sudo = getattr(config, "SUDO_USERS", []) or []
    if not sudo:
        return True
    return user_id in sudo

def can_use(user_id: int) -> bool:
    if BOT_PUBLIC:
        return True
    return is_owner(user_id)

def fmt_duration(sec):
    if not sec:
        return "00:00"
    try:
        sec = int(sec)
    except Exception:
        return "00:00"
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def requester_name(user):
    if not user:
        return "User"
    if user.username:
        return f"@{user.username}"
    name = (user.first_name or "") + ((" " + user.last_name) if user.last_name else "")
    return clean_name(name) or "User"

def build_player_keyboard(paused=False, queue_len=0, autoplay=False):
    ap = "ON" if autoplay else "OFF"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶", callback_data="ctl|resume"),
            InlineKeyboardButton("Ⅱ", callback_data="ctl|pause"),
            InlineKeyboardButton("↻", callback_data="ctl|replay"),
            InlineKeyboardButton("⏭", callback_data="ctl|skip"),
            InlineKeyboardButton("⏹", callback_data="ctl|stop"),
        ],
        [InlineKeyboardButton(f"🔍 AUTOPLAY : {ap}", callback_data="ctl|autoplay")],
        [
            InlineKeyboardButton("« 10s", callback_data="ctl|seekback"),
            InlineKeyboardButton("10s »", callback_data="ctl|seekfwd"),
        ],
        [InlineKeyboardButton("🎵 Close", callback_data="ctl|close")],
    ])

def start_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Song", callback_data="help|song"),
            InlineKeyboardButton("🎬 Movie", callback_data="help|movie"),
            InlineKeyboardButton("🔞 Adult", callback_data="help|adult"),
        ],
        [
            InlineKeyboardButton("⏯ Controls", callback_data="help|ctrl"),
            InlineKeyboardButton("📖 Help", callback_data="help|full"),
        ],
    ])

async def reply_rich_or_text(message, html, plain, reply_markup=None):
    ok = await send_rich(message.chat.id, html, reply_markup=None)
    if ok:
        return True
    await message.reply_text(plain, reply_markup=reply_markup)
    return False

async def send_now_playing(chat_id, title, duration=0, requester="User", queued=False, thumb="", edit_msg=None):
    state = get_state(chat_id)
    qlen = len(state.get("queue") or [])
    ap = bool(state.get("autoplay"))
    if duration:
        state["duration"] = int(duration)
    plain = plain_now_playing(title, duration, requester, queued, qlen, pos=0, autoplay=ap)
    kb_api = None if queued else player_keyboard_api(paused=False, autoplay=ap, duration=duration or 0, pos=0)

    result = await send_message_styled(chat_id, plain, reply_markup=kb_api)
    if result:
        if edit_msg:
            try:
                await edit_msg.delete()
            except Exception:
                pass
        class _Msg:
            pass
        msg = _Msg()
        msg.id = result.get("message_id")
        if not queued and duration and duration > 0:
            await start_progress(client, chat_id, msg, title, duration, requester, get_state)
        return True

    kb = None if queued else build_player_keyboard(paused=False, queue_len=qlen, autoplay=ap)
    msg = None
    if edit_msg:
        try:
            msg = await edit_msg.edit_text(plain, reply_markup=kb)
        except Exception:
            msg = None
    if msg is None:
        try:
            msg = await client.send_message(chat_id, plain, reply_markup=kb)
            if edit_msg:
                try:
                    await edit_msg.delete()
                except Exception:
                    pass
        except Exception as e:
            print(f"send_now_playing fail: {e}")
            return False
    if not queued and duration and duration > 0 and msg:
        await start_progress(client, chat_id, msg, title, duration, requester, get_state)
    return True

async def play_yt_result(chat_id, info):
    title = (info.get("title") or "YouTube")[:60]
    if info.get("is_local") or (info.get("path") and os.path.isfile(info.get("path", ""))):
        path = info.get("path") or info.get("url")
        return await play_local_file(chat_id, path, title)
    return await play_remote_url(chat_id, info["url"], title)

if getattr(config, "BOT_TOKEN", None):
    bot = Client("MusicPlayer", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN, in_memory=True)
    client = bot
else:
    from core.stream import app
    client = app

PREFIXES = getattr(config, "PREFIXES", ["!", "/", "."])

# Rest of handlers loaded from backup module if present
print("WARN: partial main — deploying full file next")
