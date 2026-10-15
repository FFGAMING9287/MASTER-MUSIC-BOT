"""
Music Player + Movie + Adult + YouTube Bot
Features: skip, pause, resume, queue, public/private mode, yt-dlp YouTube
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
        return "?"
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"

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

# ==================== BASIC ====================

@client.on_message(filters.command(["start"], PREFIXES) & ~filters.bot)
@handle_error
async def start(_, message: Message):
    name = message.from_user.mention if message.from_user else "User"
    mode = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
    await message.reply_text(
        f"Hello {name}!\n\n**FFGAMING X MUSIC BOT**\nMode: {mode}\n\n"
        "🎵 /song or /yt <name> - YouTube music\n"
        "🎬 /play /movie - Movies\n"
        "🔞 /adult /xxx - Adult\n"
        "⏯ /skip /pause /resume /stop /queue\n"
        "🔐 /mode public|private (owner)\n"
        "/help /ping"
    )

@client.on_message(filters.command("help", PREFIXES) & ~filters.bot)
@handle_error
async def help_cmd(_, message: Message):
    mode = "Public" if BOT_PUBLIC else "Private"
    await message.reply_text(
        f"**Commands** (Mode: {mode})\n\n"
        "🎵 **YouTube Music**\n"
        "/song <name> or /yt <name>\n"
        "/music <name>\n\n"
        "🎬 **Movies**\n"
        "/play <name> /movie <name>\n\n"
        "🔞 **Adult**\n"
        "/adult or /xxx <query>\n\n"
        "⏯ **Controls**\n"
        "/skip /next · /pause · /resume\n"
        "/stop · /queue /q\n\n"
        "🔐 **Owner**\n"
        "/mode public | private"
    )

@client.on_message(filters.command("ping", PREFIXES) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await message.reply_text("🤖 **Pong!**")

# ==================== MODE ====================

@client.on_message(filters.command("mode", PREFIXES) & ~filters.bot)
@handle_error
async def mode_cmd(_, message: Message):
    global BOT_PUBLIC
    user_id = message.from_user.id if message.from_user else 0
    if not is_owner(user_id):
        await message.reply_text("❌ Only the bot owner can change mode.")
        return
    arg = extract_args(message.text).lower().strip()
    if arg in ("public", "on", "open"):
        BOT_PUBLIC = True
        await message.reply_text("🌐 **Public mode ON**")
    elif arg in ("private", "off", "lock"):
        BOT_PUBLIC = False
        await message.reply_text("🔒 **Private mode ON**")
    else:
        status = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
        await message.reply_text(f"Current mode: **{status}**\n\n/mode public\n/mode private")

# ==================== CONTROLS ====================

@client.on_message(filters.command(["skip", "next"], PREFIXES) & ~filters.private)
@handle_error
async def skip_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        await message.reply_text("🔒 Private mode.")
        return
    ok, msg = await skip_stream(message.chat.id)
    await message.reply_text(msg)

@client.on_message(filters.command("pause", PREFIXES) & ~filters.private)
@handle_error
async def pause_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        await message.reply_text("🔒 Private mode.")
        return
    ok, msg = await pause_stream(message.chat.id)
    await message.reply_text(msg)

@client.on_message(filters.command("resume", PREFIXES) & ~filters.private)
@handle_error
async def resume_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        await message.reply_text("🔒 Private mode.")
        return
    ok, msg = await resume_stream(message.chat.id)
    await message.reply_text(msg)

@client.on_message(filters.command(["stop", "end"], PREFIXES) & ~filters.private)
@handle_error
async def stop_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        await message.reply_text("🔒 Private mode.")
        return
    ok, msg = await stop_stream(message.chat.id)
    await message.reply_text(msg)

@client.on_message(filters.command(["queue", "q"], PREFIXES) & ~filters.private)
@handle_error
async def queue_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        await message.reply_text("🔒 Private mode.")
        return
    await message.reply_text(get_queue_text(message.chat.id))

# ==================== YOUTUBE MUSIC ====================

@client.on_message(filters.command(["song", "yt", "music", "s"], PREFIXES) & ~filters.private)
@register
@handle_error
async def song_cmd(_, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not can_use(user_id):
        await message.reply_text("🔒 Bot is in **Private mode**.")
        return
    query = extract_args(message.text)
    if not query:
        await message.reply_text("Usage: /song <name> or /yt <YouTube link>")
        return

    status = await message.reply_text("🔍 Searching YouTube...")

    # Direct link?
    if "youtube.com" in query or "youtu.be" in query:
        await status.edit_text("⬇️ Getting stream...")
        info = await get_stream_info(query)
        if not info:
            await status.edit_text("❌ Could not get stream. Try another link.")
            return
        await status.edit_text(f"▶️ Playing **{info['title'][:50]}**...")
        ok, msg = await play_remote_url(message.chat.id, info["url"], info["title"][:60])
        await status.edit_text(f"{'✅' if ok else '❌'} {msg}")
        return

    results = await search_youtube(query, limit=6)
    if not results:
        await status.edit_text("❌ No results found on YouTube.")
        return

    yt_cache[message.chat.id] = results
    text = f"🎵 **YouTube results for:** `{query}`\n\nChoose a song:"
    await status.edit_text(text, reply_markup=build_yt_keyboard(results))

@client.on_callback_query(filters.regex(r"^yt\|"))
@handle_error
async def yt_callback(_, callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    if not can_use(user_id):
        await callback.answer("Private mode", show_alert=True)
        return
    idx = int(callback.data.split("|")[1])
    chat_id = callback.message.chat.id
    results = yt_cache.get(chat_id)
    if not results or idx >= len(results):
        await callback.answer("Expired", show_alert=True)
        return

    item = results[idx]
    await callback.answer("Loading...")
    status = await callback.message.reply_text(f"⬇️ Getting stream:\n**{item['title'][:50]}**")

    info = await get_stream_info(item["url"])
    if not info:
        await status.edit_text("❌ Failed to get stream URL. Try another.")
        return

    ok, msg = await play_remote_url(chat_id, info["url"], info["title"][:60])
    if ok:
        await status.edit_text(
            f"✅ **{msg}**\n"
            f"⏱ {fmt_duration(info.get('duration'))}\n"
            f"👤 {info.get('uploader', '')[:40]}"
        )
    else:
        await status.edit_text(f"❌ {msg}")

# ==================== MOVIES ====================

@client.on_message(filters.command(["movie", "mv"], PREFIXES) & ~filters.private)
@register
@handle_error
async def movie_cmd(_, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not can_use(user_id):
        await message.reply_text("🔒 Private mode.")
        return
    query = extract_args(message.text)
    if not query:
        await message.reply_text("Usage: /movie <name>")
        return
    status = await message.reply_text("🔍 Searching movies...")
    data = await search_movie(query)
    if not data or not data.get("results"):
        await status.edit_text("❌ No results found.")
        return
    movie_cache[message.chat.id] = {"data": data, "page": 0}
    result = data["results"][0]
    text = f"🎬 **{result.get('title')}** ({result.get('year')}) · {result.get('type')}\n⭐ {result.get('rating','N/A')}/10\n📺 {len(result.get('episodes',[]))} episodes\n\nChoose episode:"
    await status.edit_text(text, reply_markup=build_movie_keyboard(data, 0))

@client.on_message(filters.command(["p", "play"], PREFIXES) & ~filters.private)
@register
@handle_error
async def play_cmd(_, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not can_use(user_id):
        await message.reply_text("🔒 Private mode.")
        return
    query = extract_args(message.text)
    if not query:
        await message.reply_text("Usage: /play <name>\nTip: use /song for YouTube music")
        return
    status = await message.reply_text("🔍 Searching...")
    data = await search_movie(query)
    if data and data.get("results"):
        movie_cache[message.chat.id] = {"data": data, "page": 0}
        result = data["results"][0]
        text = f"🎬 **{result.get('title')}** ({result.get('year')})\n⭐ {result.get('rating','N/A')}/10\n📺 {len(result.get('episodes',[]))} episodes\n\nChoose episode:"
        await status.edit_text(text, reply_markup=build_movie_keyboard(data, 0))
        return
    await status.edit_text(f"No movie found.\nTry /song {query} for YouTube music.")

# ==================== ADULT ====================

@client.on_message(filters.command(["adult", "xxx", "nsfw"], PREFIXES) & ~filters.private)
@register
@handle_error
async def adult_cmd(_, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not can_use(user_id):
        await message.reply_text("🔒 Private mode.")
        return
    query = extract_args(message.text)
    if not query:
        await message.reply_text("Usage: /adult <query> or /xxx <query>")
        return
    status = await message.reply_text("🔍 Searching adult content...")
    data = await search_adult(query)
    if not data or not data.get("items"):
        await status.edit_text("❌ No results found.")
        return
    items = data["items"]
    adult_cache[message.chat.id] = {"items": items, "page": 0}
    text = f"🔞 **Adult Search**\n\nFound **{len(items)}** results for: `{query}`\n\nChoose a video:"
    await status.edit_text(text, reply_markup=build_adult_keyboard(items, 0))

# ==================== CALLBACKS ====================

@client.on_callback_query(filters.regex(r"^mvpage\|"))
@handle_error
async def page_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        await callback.answer("Private mode", show_alert=True)
        return
    page = int(callback.data.split("|")[1])
    chat_id = callback.message.chat.id
    cached = movie_cache.get(chat_id)
    if not cached:
        await callback.answer("Search expired")
        return
    data = cached["data"]
    cached["page"] = page
    result = data["results"][0]
    text = f"🎬 **{result.get('title')}** ({result.get('year')})\nPage {page+1}"
    await callback.message.edit_text(text, reply_markup=build_movie_keyboard(data, page))
    await callback.answer()

@client.on_callback_query(filters.regex(r"^adpage\|"))
@handle_error
async def adult_page_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        await callback.answer("Private mode", show_alert=True)
        return
    page = int(callback.data.split("|")[1])
    chat_id = callback.message.chat.id
    cached = adult_cache.get(chat_id)
    if not cached:
        await callback.answer("Search expired")
        return
    items = cached["items"]
    cached["page"] = page
    text = f"🔞 **Adult Search**\nPage {page+1} · {len(items)} results"
    await callback.message.edit_text(text, reply_markup=build_adult_keyboard(items, page))
    await callback.answer()

@client.on_callback_query(filters.regex(r"^mv\|"))
@handle_error
async def movie_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        await callback.answer("Private mode", show_alert=True)
        return
    parts = callback.data.split("|")
    if len(parts) < 6:
        await callback.answer("Invalid")
        return
    _, mid, season, episode, short_lang, quality = parts
    await callback.answer(f"Downloading S{season}E{episode}...")
    chat_id = callback.message.chat.id
    cached = movie_cache.get(chat_id)
    if not cached:
        await callback.message.reply_text("Search expired.")
        return
    data = cached["data"]
    download_url = None
    title = "Unknown"
    for res in data.get("results", []):
        title = res.get("title", "Unknown")
        for ep in res.get("episodes", []):
            if str(ep.get("episode")) == str(episode) and str(ep.get("season",1)) == str(season):
                for q in ep.get("qualities", []):
                    if q.get("quality") == quality:
                        download_url = q.get("download_url") or q.get("downloadUrl")
                        break
                if download_url:
                    break
        if download_url:
            break
    if not download_url:
        await callback.message.reply_text("❌ Link not found.")
        return

    status = await callback.message.reply_text(f"⬇️ Downloading **{title}** S{season}E{episode}...")
    filename = f"{title.replace(' ','_')}_s{season}e{episode}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)
    if not local_path:
        await status.edit_text(f"❌ Download failed.\n{info}")
        return
    size = os.path.getsize(local_path) / (1024*1024)
    await status.edit_text(f"✅ Downloaded ({size:.1f} MB)\n▶️ Playing...")
    success, msg = await play_local_file(chat_id, local_path, f"{title} S{season}E{episode}")
    await status.edit_text(f"{'✅' if success else '❌'} **{msg}**\n📦 {size:.1f} MB")

@client.on_callback_query(filters.regex(r"^ad\|"))
@handle_error
async def adult_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        await callback.answer("Private mode", show_alert=True)
        return
    parts = callback.data.split("|")
    if len(parts) < 3:
        await callback.answer("Invalid")
        return
    idx = int(parts[2])
    chat_id = callback.message.chat.id
    cached = adult_cache.get(chat_id)
    if not cached or idx >= len(cached["items"]):
        await callback.answer("Expired")
        return

    item = cached["items"][idx]
    title = item.get("title", "Video")
    quality = item.get("quality", "?")
    download_url = item.get("downloadUrl") or item.get("download_url")
    if not download_url:
        await callback.message.reply_text("❌ No download link.")
        return

    await callback.answer(f"Downloading {quality}...")
    status = await callback.message.reply_text(f"⬇️ Downloading:\n**{title[:60]}**")
    filename = f"adult_{idx}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)
    if not local_path:
        await status.edit_text(f"❌ Download failed.\n{info}")
        return
    size = os.path.getsize(local_path) / (1024*1024)
    await status.edit_text(f"✅ Downloaded ({size:.1f} MB)\n▶️ Playing...")
    success, msg = await play_local_file(chat_id, local_path, title[:40])
    await status.edit_text(f"{'✅' if success else '❌'} **{msg}**\n📦 {size:.1f} MB")

print("Bot loaded: YouTube + Movie + Adult + Controls")
if __name__ == "__main__":
    client.run()
