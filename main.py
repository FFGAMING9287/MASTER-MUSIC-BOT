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
    plain = plain_now_playing(title, duration, requester, queued, qlen, pos=0, autoplay=ap)
    kb_api = None if queued else player_keyboard_api(paused=False, autoplay=ap)

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

def build_movie_keyboard(data, page=0):
    if not data or not data.get("results"):
        return None
    result = data["results"][0]
    episodes = result.get("episodes", [])
    buttons = []
    start = page * 8
    end = start + 8
    for ep in episodes[start:end]:
        for q in ep.get("qualities", [])[:2]:
            lang = ep.get("language", "?")
            label = f"▶ S{ep.get('season',1)}E{ep['episode']} {lang} {q['quality']}"
            short_lang = (lang or "unk")[:4].lower()
            cb = f"mv|{result.get('id','x')}|{ep.get('season',1)}|{ep['episode']}|{short_lang}|{q['quality']}"
            buttons.append([InlineKeyboardButton(label[:58], callback_data=cb[:64])])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Prev", callback_data=f"mvpage|{page-1}"))
    if end < len(episodes):
        nav.append(InlineKeyboardButton("Next →", callback_data=f"mvpage|{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons) if buttons else None

def build_adult_keyboard(items, page=0):
    buttons = []
    start = page * 6
    end = start + 6
    for i, item in enumerate(items[start:end]):
        title = (item.get("title") or "Video")[:40]
        quality = item.get("quality", "?")
        size = item.get("size", "?")
        label = f"▶ {title} [{quality}] {size}"
        cb = f"ad|{page}|{start+i}"
        buttons.append([InlineKeyboardButton(label[:58], callback_data=cb[:64])])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Prev", callback_data=f"adpage|{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton("Next →", callback_data=f"adpage|{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons) if buttons else None

def build_yt_keyboard(items):
    buttons = []
    for i, item in enumerate(items[:8]):
        title = (item.get("title") or "Song")[:42]
        dur = fmt_duration(item.get("duration"))
        label = f"▶ {title} [{dur}]"
        buttons.append([InlineKeyboardButton(label[:58], callback_data=f"yt|{i}")])
    return InlineKeyboardMarkup(buttons) if buttons else None

@client.on_message(filters.command(["start"], PREFIXES) & ~filters.bot)
@handle_error
async def start(_, message: Message):
    name = clean_name(message.from_user.first_name if message.from_user else "User")
    mode = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
    plain = f"🎧 **FFGAMING X MUSIC BOT**\n\n👋 Hello **{name}**!\n🔐 Mode : `{mode}`\n\n🎵 /song /yt · 🎬 /play /movie · 🔞 /adult\n⏯ /skip /pause /resume /stop /queue\n🔐 /mode public|private"
    await reply_rich_or_text(message, html_start(name, mode), plain, start_keyboard())

@client.on_message(filters.command("help", PREFIXES) & ~filters.bot)
@handle_error
async def help_cmd(_, message: Message):
    mode = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
    plain = f"📖 **Commands**\nMode: `{mode}`\n\n/song /yt · /play /movie · /adult\n/skip /pause /resume /stop /queue\n/mode public|private"
    await reply_rich_or_text(message, html_help(mode), plain, start_keyboard())

@client.on_callback_query(filters.regex(r"^help\|"))
@handle_error
async def help_callback(_, callback: CallbackQuery):
    section = callback.data.split("|")[1]
    map_html = {
        "song": html_info("🎵 YouTube Music", "<code>/song <name></code><br/><code>/yt <link></code>"),
        "movie": html_info("🎬 Movies", "<code>/play <name></code><br/><code>/movie <name></code>"),
        "adult": html_info("🔞 Adult", "<code>/adult <query></code><br/><code>/xxx <query></code>"),
        "ctrl": html_info("⏯ Controls", "▶ Ⅱ ↻ ⏭ ⏹ · Autoplay · «10s · Close"),
        "full": html_help("🌐 Public" if BOT_PUBLIC else "🔒 Private"),
    }
    plain_map = {
        "song": "🎵 **YouTube**\n`/song <name>`\n`/yt <link>`",
        "movie": "🎬 **Movies**\n`/play` `/movie`",
        "adult": "🔞 **Adult**\n`/adult` `/xxx`",
        "ctrl": "⏯ **Controls**\n▶ pause skip stop · autoplay · seek",
        "full": "📖 **Help**\n/song /yt · /play /movie · /adult",
    }
    html = map_html.get(section, map_html["full"])
    plain = plain_map.get(section, plain_map["full"])
    await callback.answer()
    ok = await send_rich(callback.message.chat.id, html, reply_markup=None)
    if not ok:
        try:
            await callback.message.edit_text(plain, reply_markup=start_keyboard())
        except Exception:
            await callback.message.reply_text(plain, reply_markup=start_keyboard())

@client.on_message(filters.command("ping", PREFIXES) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await reply_rich_or_text(message, html_ping(), "🤖 **Pong!**\n✅ Bot online")

@client.on_message(filters.command("mode", PREFIXES) & ~filters.bot)
@handle_error
async def mode_cmd(_, message: Message):
    global BOT_PUBLIC
    if not is_owner(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Owner only"), "🔒 **Owner Only**")
    arg = extract_args(message.text).lower().strip()
    if arg in ("public", "on", "open"):
        BOT_PUBLIC = True
        await reply_rich_or_text(message, html_mode("🌐 Public", "Everyone can use the bot."), "🌐 **Public Mode ON**")
    elif arg in ("private", "off", "lock"):
        BOT_PUBLIC = False
        await reply_rich_or_text(message, html_mode("🔒 Private", "Only owner can use features."), "🔒 **Private Mode ON**")
    else:
        status = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
        await reply_rich_or_text(message, html_mode(status, "<code>/mode public</code> | <code>private</code>"), f"🔐 Mode: `{status}`")

@client.on_message(filters.command(["skip", "next"], PREFIXES) & ~filters.private)
@handle_error
async def skip_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    cancel_progress(message.chat.id)
    ok, msg = await skip_stream(message.chat.id)
    await reply_rich_or_text(message, html_info("⏭ Skip", msg), f"⏭ {msg}")

@client.on_message(filters.command("pause", PREFIXES) & ~filters.private)
@handle_error
async def pause_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    on_pause(message.chat.id, get_state)
    ok, msg = await pause_stream(message.chat.id)
    await reply_rich_or_text(message, html_info("⏸ Pause", msg), msg)

@client.on_message(filters.command("resume", PREFIXES) & ~filters.private)
@handle_error
async def resume_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    on_resume(message.chat.id, get_state)
    ok, msg = await resume_stream(message.chat.id)
    await reply_rich_or_text(message, html_info("▶️ Resume", msg), msg)

@client.on_message(filters.command(["stop", "end"], PREFIXES) & ~filters.private)
@handle_error
async def stop_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    cancel_progress(message.chat.id)
    ok, msg = await stop_stream(message.chat.id)
    await reply_rich_or_text(message, html_info("⏹ Stopped", msg), f"⏹ **Stopped**\n{msg}")

@client.on_message(filters.command(["queue", "q"], PREFIXES) & ~filters.private)
@handle_error
async def queue_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    body = get_queue_text(message.chat.id)
    await reply_rich_or_text(message, html_queue(body), f"☰ **Queue**\n\n{body}")

@client.on_callback_query(filters.regex(r"^ctl\|"))
@handle_error
async def control_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    action = callback.data.split("|")[1]
    chat_id = callback.message.chat.id
    state = get_state(chat_id)
    qlen = len(state.get("queue") or [])

    if action == "pause":
        on_pause(chat_id, get_state)
        ok, msg = await pause_stream(chat_id)
        await callback.answer(msg[:180] if msg else "Paused")
        if ok:
            await edit_message_styled(chat_id, callback.message.id, reply_markup=player_keyboard_api(paused=True, autoplay=bool(state.get("autoplay"))))
    elif action == "resume":
        on_resume(chat_id, get_state)
        ok, msg = await resume_stream(chat_id)
        await callback.answer(msg[:180] if msg else "Resumed")
        if ok:
            await edit_message_styled(chat_id, callback.message.id, reply_markup=player_keyboard_api(paused=False, autoplay=bool(state.get("autoplay"))))
    elif action == "skip":
        cancel_progress(chat_id)
        ok, msg = await skip_stream(chat_id)
        await callback.answer("Skipped" if ok else (msg or "")[:180])
        if not await send_rich(chat_id, html_info("⏭ Skip", msg)):
            await callback.message.reply_text(f"⏭ {msg}")
    elif action == "stop":
        cancel_progress(chat_id)
        ok, msg = await stop_stream(chat_id)
        await callback.answer("Stopped")
        if not await send_rich(chat_id, html_info("⏹ Stopped", msg)):
            await callback.message.reply_text(f"⏹ {msg}")
    elif action == "queue":
        await callback.answer()
        body = get_queue_text(chat_id)
        if not await send_rich(chat_id, html_queue(body)):
            await callback.message.reply_text(f"☰ **Queue**\n\n{body}")
    elif action == "replay":
        cancel_progress(chat_id)
        path = state.get("path")
        title = state.get("title") or "Track"
        if not path:
            return await callback.answer("Nothing to replay", show_alert=True)
        if os.path.isfile(str(path)):
            ok, msg = await play_local_file(chat_id, path, title, force=True)
        else:
            ok, msg = await play_remote_url(chat_id, path, title, force=True)
        await callback.answer("Replaying..." if ok else (msg or "")[:180])
        if ok:
            dur = await duration_from_file(path) if os.path.isfile(str(path)) else (state.get("duration") or 0)
            await send_now_playing(chat_id, title, dur, requester_name(callback.from_user))
    elif action == "autoplay":
        state["autoplay"] = not bool(state.get("autoplay"))
        ap = "ON" if state["autoplay"] else "OFF"
        await callback.answer(f"Autoplay : {ap}")
        await edit_message_styled(chat_id, callback.message.id, reply_markup=player_keyboard_api(paused=bool(state.get("paused")), autoplay=state["autoplay"]))
    elif action == "seekback":
        base = int(state.get("elapsed_base") or 0)
        if state.get("paused"):
            state["elapsed_base"] = max(0, base - 10)
        else:
            start = state.get("start_ts") or time.time()
            cur = base + int(time.time() - start)
            state["elapsed_base"] = max(0, cur - 10)
            state["start_ts"] = time.time()
        await callback.answer("« -10s")
    elif action == "seekfwd":
        dur = int(state.get("duration") or 0)
        base = int(state.get("elapsed_base") or 0)
        if state.get("paused"):
            state["elapsed_base"] = min(dur, base + 10) if dur else base + 10
        else:
            start = state.get("start_ts") or time.time()
            cur = base + int(time.time() - start)
            state["elapsed_base"] = min(dur, cur + 10) if dur else cur + 10
            state["start_ts"] = time.time()
        await callback.answer("+10s »")
    elif action == "close":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer("Closed")
    else:
        await callback.answer()

@client.on_message(filters.command(["song", "yt", "music", "s"], PREFIXES) & ~filters.private)
@register
@handle_error
async def song_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    query = extract_args(message.text)
    if not query:
        return await reply_rich_or_text(message, html_info("🎵 YouTube", "<code>/song <name></code>"), "🎵 `/song <name>`")
    status = await message.reply_text(status_searching("YouTube"))
    req = requester_name(message.from_user)
    if "youtube.com" in query or "youtu.be" in query:
        await status.edit_text("⬇️ Getting stream...")
        info = await get_stream_info(query)
        if not info:
            return await status.edit_text("❌ Could not get stream")
        ok, msg = await play_yt_result(message.chat.id, info)
        if not ok:
            return await status.edit_text(f"❌ {msg}")
        await send_now_playing(message.chat.id, info.get("title", "YouTube"), info.get("duration") or 0, req, "queue" in msg.lower(), info.get("thumb", ""), edit_msg=status)
        return
    results = await search_youtube(query, limit=6)
    if not results:
        return await status.edit_text("❌ No results found")
    yt_cache[message.chat.id] = results
    html = html_search("YouTube", query, len(results))
    kb = build_yt_keyboard(results)
    if not await send_rich(message.chat.id, html, kb):
        await status.edit_text(status_results("YouTube", query, len(results)), reply_markup=kb)
    else:
        try:
            await status.delete()
        except Exception:
            pass

@client.on_callback_query(filters.regex(r"^yt\|"))
@handle_error
async def yt_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    idx = int(callback.data.split("|")[1])
    chat_id = callback.message.chat.id
    results = yt_cache.get(chat_id)
    if not results or idx >= len(results):
        return await callback.answer("Expired", show_alert=True)
    item = results[idx]
    await callback.answer("Loading...")
    status = await callback.message.reply_text(status_downloading(item["title"]))
    req = requester_name(callback.from_user)
    info = await get_stream_info(item["url"])
    if not info:
        return await status.edit_text("❌ Could not get stream")
    ok, msg = await play_yt_result(chat_id, info)
    if not ok:
        return await status.edit_text(f"❌ {msg}")
    dur = info.get("duration") or item.get("duration") or 0
    await send_now_playing(chat_id, info.get("title", item["title"]), dur, req, "queue" in msg.lower(), item.get("thumb", ""), edit_msg=status)

@client.on_message(filters.command(["movie", "mv"], PREFIXES) & ~filters.private)
@register
@handle_error
async def movie_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    query = extract_args(message.text)
    if not query:
        return await reply_rich_or_text(message, html_info("🎬 Movies", "<code>/movie <name></code>"), "🎬 `/movie <name>`")
    status = await message.reply_text(status_searching("movie"))
    data = await search_movie(query)
    if not data or not data.get("results"):
        return await status.edit_text("❌ No results found")
    movie_cache[message.chat.id] = {"data": data, "page": 0}
    result = data["results"][0]
    body = f"📅 {result.get('year')} · ⭐ {result.get('rating','N/A')}/10"
    html = html_info(f"🎬 {result.get('title')}", body)
    kb = build_movie_keyboard(data, 0)
    if not await send_rich(message.chat.id, html, kb):
        await status.edit_text(f"🎬 **{result.get('title')}**\nChoose:", reply_markup=kb)
    else:
        try:
            await status.delete()
        except Exception:
            pass

@client.on_message(filters.command(["p", "play"], PREFIXES) & ~filters.private)
@register
@handle_error
async def play_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    query = extract_args(message.text)
    if not query:
        return await reply_rich_or_text(message, html_info("🎬 Play", "<code>/play <name></code>"), "🎬 `/play <name>`")
    status = await message.reply_text(status_searching("generic"))
    data = await search_movie(query)
    if data and data.get("results"):
        movie_cache[message.chat.id] = {"data": data, "page": 0}
        result = data["results"][0]
        html = html_info(f"🎬 {result.get('title')}", f"📅 {result.get('year')}")
        kb = build_movie_keyboard(data, 0)
        if not await send_rich(message.chat.id, html, kb):
            await status.edit_text(f"🎬 **{result.get('title')}**\nChoose:", reply_markup=kb)
        else:
            try:
                await status.delete()
            except Exception:
                pass
        return
    await status.edit_text(f"❌ No movie.\nTry `/song {query}`")

@client.on_message(filters.command(["adult", "xxx", "nsfw"], PREFIXES) & ~filters.private)
@register
@handle_error
async def adult_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(message, html_error("Private mode"), "🔒 Private mode")
    query = extract_args(message.text)
    if not query:
        return await reply_rich_or_text(message, html_info("🔞 Adult", "<code>/adult <query></code>"), "🔞 `/adult <query>`")
    status = await message.reply_text(status_searching("adult"))
    data = await search_adult(query)
    if not data or not data.get("items"):
        return await status.edit_text("❌ No results found")
    items = data["items"]
    adult_cache[message.chat.id] = {"items": items, "page": 0}
    html = html_search("Adult", query, len(items))
    kb = build_adult_keyboard(items, 0)
    if not await send_rich(message.chat.id, html, kb):
        await status.edit_text(status_results("Adult", query, len(items)), reply_markup=kb)
    else:
        try:
            await status.delete()
        except Exception:
            pass

@client.on_callback_query(filters.regex(r"^mvpage\|"))
@handle_error
async def page_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    page = int(callback.data.split("|")[1])
    cached = movie_cache.get(callback.message.chat.id)
    if not cached:
        return await callback.answer("Expired")
    data = cached["data"]
    cached["page"] = page
    result = data["results"][0]
    await callback.message.edit_text(f"🎬 **{result.get('title')}** · Page `{page+1}`\n\nChoose:", reply_markup=build_movie_keyboard(data, page))
    await callback.answer()

@client.on_callback_query(filters.regex(r"^adpage\|"))
@handle_error
async def adult_page_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    page = int(callback.data.split("|")[1])
    cached = adult_cache.get(callback.message.chat.id)
    if not cached:
        return await callback.answer("Expired")
    items = cached["items"]
    cached["page"] = page
    await callback.message.edit_text(f"🔞 Page `{page+1}` · **{len(items)}**\n\nChoose:", reply_markup=build_adult_keyboard(items, page))
    await callback.answer()

@client.on_callback_query(filters.regex(r"^mv\|"))
@handle_error
async def movie_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    parts = callback.data.split("|")
    if len(parts) < 6:
        return await callback.answer("Invalid")
    _, mid, season, episode, short_lang, quality = parts
    await callback.answer("Downloading...")
    chat_id = callback.message.chat.id
    cached = movie_cache.get(chat_id)
    if not cached:
        return await callback.message.reply_text("❌ Search expired.")
    data = cached["data"]
    download_url = None
    title = "Unknown"
    for res in data.get("results", []):
        title = res.get("title", "Unknown")
        for ep in res.get("episodes", []):
            if str(ep.get("episode")) == str(episode) and str(ep.get("season", 1)) == str(season):
                for q in ep.get("qualities", []):
                    if q.get("quality") == quality:
                        download_url = q.get("download_url") or q.get("downloadUrl")
                        break
                if download_url:
                    break
        if download_url:
            break
    if not download_url:
        return await callback.message.reply_text("❌ Link not found.")
    req = requester_name(callback.from_user)
    status = await callback.message.reply_text(status_downloading(f"{title} S{season}E{episode}", quality))
    filename = f"{title.replace(' ', '_')}_s{season}e{episode}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)
    if not local_path:
        return await status.edit_text(f"❌ Download failed\n{info}")
    success, msg = await play_local_file(chat_id, local_path, f"{title} S{season}E{episode}")
    if not success:
        return await status.edit_text(f"❌ {msg}")
    dur = await duration_from_file(local_path)
    await send_now_playing(chat_id, f"{title} S{season}E{episode}", dur, req, "queue" in msg.lower(), edit_msg=status)

@client.on_callback_query(filters.regex(r"^ad\|"))
@handle_error
async def adult_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    parts = callback.data.split("|")
    if len(parts) < 3:
        return await callback.answer("Invalid")
    idx = int(parts[2])
    chat_id = callback.message.chat.id
    cached = adult_cache.get(chat_id)
    if not cached or idx >= len(cached["items"]):
        return await callback.answer("Expired")
    item = cached["items"][idx]
    title = item.get("title", "Video")
    quality = item.get("quality", "?")
    download_url = item.get("downloadUrl") or item.get("download_url")
    thumb = item.get("thumbnail") or item.get("thumb") or item.get("image") or ""
    if not download_url:
        return await callback.message.reply_text("❌ No download link.")
    await callback.answer("Downloading...")
    req = requester_name(callback.from_user)
    status = await callback.message.reply_text(status_downloading(title, quality))
    filename = f"adult_{idx}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)
    if not local_path:
        return await status.edit_text(f"❌ Download failed\n{info}")
    success, msg = await play_local_file(chat_id, local_path, title[:40])
    if not success:
        return await status.edit_text(f"❌ {msg}")
    dur = duration_from_item(item) or await duration_from_file(local_path)
    await send_now_playing(chat_id, title[:50], dur, req, "queue" in msg.lower(), thumb=thumb, edit_msg=status)

print("Bot loaded: Yoru-style colored buttons (FFGAMING)")
if __name__ == "__main__":
    client.run()
