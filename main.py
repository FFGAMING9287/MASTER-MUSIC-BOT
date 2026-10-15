"""
Music Player bot - Game Over style Now Playing card
"""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import os
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
    send_rich_now_playing,
    send_photo_now_playing,
    plain_now_playing,
    clean_name,
)
from core.duration import duration_from_file, duration_from_item

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

def build_player_keyboard(paused=False, queue_len=0):
    mid = (
        InlineKeyboardButton("Ⅱ Pause", callback_data="ctl|pause")
        if not paused
        else InlineKeyboardButton("▶ Resume", callback_data="ctl|resume")
    )
    qlabel = f"☰ Queue · {queue_len}"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("↻ Replay", callback_data="ctl|replay"),
            mid,
            InlineKeyboardButton("≫ Skip", callback_data="ctl|skip"),
        ],
        [
            InlineKeyboardButton(qlabel, callback_data="ctl|queue"),
            InlineKeyboardButton("⏹ Stop", callback_data="ctl|stop"),
        ],
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

async def send_now_playing(chat_id, title, duration=0, requester="User", queued=False, thumb="", edit_msg=None):
    state = get_state(chat_id)
    qlen = len(state.get("queue") or [])
    kb = build_player_keyboard(paused=False, queue_len=qlen)

    # 1) Photo + caption (closest to Game Over Musics look)
    if thumb and str(thumb).startswith("http"):
        ok = await send_photo_now_playing(chat_id, title, duration, requester, queued, thumb, reply_markup=kb)
        if ok:
            if edit_msg:
                try:
                    await edit_msg.delete()
                except Exception:
                    pass
            return True

    # 2) Rich message
    ok = await send_rich_now_playing(chat_id, title, duration, requester, queued, thumb, reply_markup=kb)
    if ok:
        if edit_msg:
            try:
                await edit_msg.delete()
            except Exception:
                pass
        return True

    # 3) Plain text
    text = plain_now_playing(title, duration, requester, queued, qlen)
    if edit_msg:
        try:
            await edit_msg.edit_text(text, reply_markup=kb)
            return True
        except Exception:
            pass
    try:
        await client.send_message(chat_id, text, reply_markup=kb)
        return True
    except Exception as e:
        print(f"send_now_playing fail: {e}")
        return False

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
    text = (
        f"🎧 **Welcome to FFGAMING X MUSIC BOT**\n\n"
        f"👋 Hello **{name}**!\n"
        f"🔐 Mode : `{mode}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵 **Music**\n`/song` `/yt` `<name or link>`\n\n"
        f"🎬 **Movies**\n`/play` `/movie` `<name>`\n\n"
        f"🔞 **Adult**\n`/adult` `/xxx` `<query>`\n\n"
        f"⏯ **Controls**\n`/skip` `/pause` `/resume` `/stop` `/queue`\n\n"
        f"🔐 **Owner**\n`/mode public` | `/mode private`\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"😌 Sit back, relax & enjoy"
    )
    await message.reply_text(text, reply_markup=start_keyboard())

@client.on_message(filters.command("help", PREFIXES) & ~filters.bot)
@handle_error
async def help_cmd(_, message: Message):
    mode = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
    text = (
        f"📖 **Command Guide**\nMode : `{mode}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵 **YouTube** — `/song` `/yt`\n"
        f"🎬 **Movies** — `/play` `/movie`\n"
        f"🔞 **Adult** — `/adult` `/xxx`\n"
        f"⏯ **Controls** — `/skip` `/pause` `/resume` `/stop` `/queue`\n"
        f"🔐 **Owner** — `/mode public|private`\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    await message.reply_text(text, reply_markup=start_keyboard())

@client.on_callback_query(filters.regex(r"^help\|"))
@handle_error
async def help_callback(_, callback: CallbackQuery):
    section = callback.data.split("|")[1]
    texts = {
        "song": "🎵 **YouTube Music**\n\n`/song <name>`\n`/yt <link>`",
        "movie": "🎬 **Movies**\n\n`/play <name>`\n`/movie <name>`",
        "adult": "🔞 **Adult**\n\n`/adult <query>`\n`/xxx <query>`",
        "ctrl": "⏯ **Controls**\n\n`/skip` `/pause` `/resume` `/stop` `/queue`",
        "full": "📖 **Full Help**\n\n🎵 `/song` `/yt`\n🎬 `/play` `/movie`\n🔞 `/adult` `/xxx`\n⏯ `/skip` `/pause` `/resume` `/stop` `/queue`\n🔐 `/mode public|private`",
    }
    text = texts.get(section, texts["full"])
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=start_keyboard())
    except Exception:
        await callback.message.reply_text(text, reply_markup=start_keyboard())

@client.on_message(filters.command("ping", PREFIXES) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await message.reply_text("🤖 **Pong!**\n\n✅ Bot online")

@client.on_message(filters.command("mode", PREFIXES) & ~filters.bot)
@handle_error
async def mode_cmd(_, message: Message):
    global BOT_PUBLIC
    if not is_owner(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Owner Only**")
    arg = extract_args(message.text).lower().strip()
    if arg in ("public", "on", "open"):
        BOT_PUBLIC = True
        await message.reply_text("🌐 **Public Mode ON**")
    elif arg in ("private", "off", "lock"):
        BOT_PUBLIC = False
        await message.reply_text("🔒 **Private Mode ON**")
    else:
        status = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
        await message.reply_text(f"🔐 **Mode** : `{status}`")

@client.on_message(filters.command(["skip", "next"], PREFIXES) & ~filters.private)
@handle_error
async def skip_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    ok, msg = await skip_stream(message.chat.id)
    await message.reply_text(f"⏭ {msg}")

@client.on_message(filters.command("pause", PREFIXES) & ~filters.private)
@handle_error
async def pause_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    ok, msg = await pause_stream(message.chat.id)
    await message.reply_text(msg)

@client.on_message(filters.command("resume", PREFIXES) & ~filters.private)
@handle_error
async def resume_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    ok, msg = await resume_stream(message.chat.id)
    await message.reply_text(msg)

@client.on_message(filters.command(["stop", "end"], PREFIXES) & ~filters.private)
@handle_error
async def stop_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    ok, msg = await stop_stream(message.chat.id)
    await message.reply_text(f"⏹ **Stopped**\n\n{msg}")

@client.on_message(filters.command(["queue", "q"], PREFIXES) & ~filters.private)
@handle_error
async def queue_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    await message.reply_text(f"☰ **Queue**\n\n{get_queue_text(message.chat.id)}")

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
        ok, msg = await pause_stream(chat_id)
        await callback.answer(msg[:180] if msg else "Paused")
        if ok:
            try:
                await callback.message.edit_reply_markup(build_player_keyboard(paused=True, queue_len=qlen))
            except Exception:
                pass
    elif action == "resume":
        ok, msg = await resume_stream(chat_id)
        await callback.answer(msg[:180] if msg else "Resumed")
        if ok:
            try:
                await callback.message.edit_reply_markup(build_player_keyboard(paused=False, queue_len=qlen))
            except Exception:
                pass
    elif action == "skip":
        ok, msg = await skip_stream(chat_id)
        await callback.answer("Skipped" if ok else (msg or "")[:180])
        await callback.message.reply_text(f"⏭ {msg}")
    elif action == "stop":
        ok, msg = await stop_stream(chat_id)
        await callback.answer("Stopped")
        await callback.message.reply_text(f"⏹ **Stopped**\n\n{msg}")
    elif action == "queue":
        await callback.answer()
        await callback.message.reply_text(f"☰ **Queue**\n\n{get_queue_text(chat_id)}")
    elif action == "replay":
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
            dur = await duration_from_file(path) if os.path.isfile(str(path)) else 0
            await send_now_playing(chat_id, title, dur, requester_name(callback.from_user))
    else:
        await callback.answer()

@client.on_message(filters.command(["song", "yt", "music", "s"], PREFIXES) & ~filters.private)
@register
@handle_error
async def song_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    query = extract_args(message.text)
    if not query:
        return await message.reply_text("🎵 **YouTube**\n\n`/song <name>`\n`/yt <link>`")

    status = await message.reply_text("🔍 **Searching YouTube...**")
    req = requester_name(message.from_user)

    if "youtube.com" in query or "youtu.be" in query:
        await status.edit_text("⬇️ **Getting stream...**")
        info = await get_stream_info(query)
        if not info:
            return await status.edit_text("❌ **Could not get stream**")
        ok, msg = await play_yt_result(message.chat.id, info)
        if not ok:
            return await status.edit_text(f"❌ {msg}")
        await send_now_playing(
            message.chat.id, info.get("title", "YouTube"),
            info.get("duration") or 0, req, "queue" in msg.lower(),
            info.get("thumb", ""), edit_msg=status,
        )
        return

    results = await search_youtube(query, limit=6)
    if not results:
        return await status.edit_text("❌ **No results found**")
    yt_cache[message.chat.id] = results
    await status.edit_text(
        f"🎵 **YouTube Results**\n\nQuery : `{query}`\nFound : **{len(results)}**\n\nChoose:",
        reply_markup=build_yt_keyboard(results),
    )

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
    status = await callback.message.reply_text(f"⬇️ **Getting stream**\n\n`{item['title'][:50]}`")
    req = requester_name(callback.from_user)

    info = await get_stream_info(item["url"])
    if not info:
        return await status.edit_text("❌ **Could not get stream**")
    ok, msg = await play_yt_result(chat_id, info)
    if not ok:
        return await status.edit_text(f"❌ {msg}")
    dur = info.get("duration") or item.get("duration") or 0
    await send_now_playing(
        chat_id, info.get("title", item["title"]),
        dur, req, "queue" in msg.lower(), item.get("thumb", ""), edit_msg=status,
    )

@client.on_message(filters.command(["movie", "mv"], PREFIXES) & ~filters.private)
@register
@handle_error
async def movie_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    query = extract_args(message.text)
    if not query:
        return await message.reply_text("🎬 **Movies**\n\n`/movie <name>`")
    status = await message.reply_text("🔍 **Searching movies...**")
    data = await search_movie(query)
    if not data or not data.get("results"):
        return await status.edit_text("❌ **No results found**")
    movie_cache[message.chat.id] = {"data": data, "page": 0}
    result = data["results"][0]
    await status.edit_text(
        f"🎬 **{result.get('title')}**\n\n"
        f"📅 `{result.get('year')}` · ⭐ `{result.get('rating','N/A')}/10`\n"
        f"📺 `{len(result.get('episodes',[]))}` episodes\n\nChoose:",
        reply_markup=build_movie_keyboard(data, 0),
    )

@client.on_message(filters.command(["p", "play"], PREFIXES) & ~filters.private)
@register
@handle_error
async def play_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    query = extract_args(message.text)
    if not query:
        return await message.reply_text("🎬 **Play**\n\n`/play <name>`")
    status = await message.reply_text("🔍 **Searching...**")
    data = await search_movie(query)
    if data and data.get("results"):
        movie_cache[message.chat.id] = {"data": data, "page": 0}
        result = data["results"][0]
        await status.edit_text(
            f"🎬 **{result.get('title')}**\n\n"
            f"📅 `{result.get('year')}` · ⭐ `{result.get('rating','N/A')}/10`\n"
            f"📺 `{len(result.get('episodes',[]))}` episodes\n\nChoose:",
            reply_markup=build_movie_keyboard(data, 0),
        )
        return
    await status.edit_text(f"❌ No movie.\nTry `/song {query}`")

@client.on_message(filters.command(["adult", "xxx", "nsfw"], PREFIXES) & ~filters.private)
@register
@handle_error
async def adult_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await message.reply_text("🔒 **Private mode**")
    query = extract_args(message.text)
    if not query:
        return await message.reply_text("🔞 **Adult**\n\n`/adult <query>`\n`/xxx <query>`")
    status = await message.reply_text("🔍 **Searching adult content...**")
    data = await search_adult(query)
    if not data or not data.get("items"):
        return await status.edit_text("❌ **No results found**")
    items = data["items"]
    adult_cache[message.chat.id] = {"items": items, "page": 0}
    await status.edit_text(
        f"🔞 **Adult Search**\n\nQuery : `{query}`\nFound : **{len(items)}**\n\nChoose:",
        reply_markup=build_adult_keyboard(items, 0),
    )

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
    await callback.message.edit_text(
        f"🎬 **{result.get('title')}** · Page `{page+1}`\n\nChoose:",
        reply_markup=build_movie_keyboard(data, page),
    )
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
    await callback.message.edit_text(
        f"🔞 Page `{page+1}` · **{len(items)}** results\n\nChoose:",
        reply_markup=build_adult_keyboard(items, page),
    )
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
    status = await callback.message.reply_text(
        f"⬇️ **Downloading**\n\n`{title}` · S{season}E{episode} · {quality}"
    )
    filename = f"{title.replace(' ', '_')}_s{season}e{episode}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)
    if not local_path:
        return await status.edit_text(f"❌ **Download failed**\n{info}")
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
    status = await callback.message.reply_text(
        f"⬇️ **Downloading**\n\n`{title[:55]}`\nQuality : `{quality}`"
    )
    filename = f"adult_{idx}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)
    if not local_path:
        return await status.edit_text(f"❌ **Download failed**\n{info}")
    success, msg = await play_local_file(chat_id, local_path, title[:40])
    if not success:
        return await status.edit_text(f"❌ {msg}")
    dur = duration_from_item(item) or await duration_from_file(local_path)
    await send_now_playing(chat_id, title[:50], dur, req, "queue" in msg.lower(), thumb=thumb, edit_msg=status)

print("Bot loaded: Game Over style Now Playing")
if __name__ == "__main__":
    client.run()
