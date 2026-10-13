"""
Music Player + Movie + Adult Bot
With VC play restored from original stack
"""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import os
from config import config
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters
from core.decorators import register, handle_error
from movie_api import search_movie, search_adult, download_file
from core.stream import play_local_file

movie_cache = {}
adult_cache = {}

def extract_args(text):
    parts = text.split(None, 1)
    return parts[1] if len(parts) > 1 else ""

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

@client.on_message(filters.command(["start"], PREFIXES) & ~filters.bot)
@handle_error
async def start(_, message: Message):
    name = message.from_user.mention if message.from_user else "User"
    await message.reply_text(
        f"Hello {name}!\n\n**FFGAMING X MUSIC BOT**\n\n"
        "/play <name> - Movie/Series\n"
        "/movie <name> - Movie search\n"
        "/adult or /xxx <query> - Adult content\n"
        "/help /ping"
    )

@client.on_message(filters.command("help", PREFIXES) & ~filters.bot)
@handle_error
async def help_cmd(_, message: Message):
    await message.reply_text(
        "**Commands**\n"
        "/play <name> - Search movie/series\n"
        "/movie <name> - Movie search\n"
        "/adult or /xxx <query> - Adult videos\n"
        "/ping\n/start"
    )

@client.on_message(filters.command("ping", PREFIXES) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await message.reply_text("🤖 **Pong!**")

@client.on_message(filters.command(["movie", "mv"], PREFIXES) & ~filters.private)
@register
@handle_error
async def movie_cmd(_, message: Message):
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
    text = f"🎬 **{result.get('title')}** ({result.get('year')}) · {result.get('type')}\n⭐ {result.get('rating','N/A')}/10\n🌐 {result.get('country','')}\n📺 {len(result.get('episodes',[]))} episodes\n\nChoose episode:"
    await status.edit_text(text, reply_markup=build_movie_keyboard(data, 0))

@client.on_message(filters.command(["p", "play"], PREFIXES) & ~filters.private)
@register
@handle_error
async def play_cmd(_, message: Message):
    query = extract_args(message.text)
    if not query:
        await message.reply_text("Usage: /play <name>")
        return
    status = await message.reply_text("🔍 Searching...")
    data = await search_movie(query)
    if data and data.get("results"):
        movie_cache[message.chat.id] = {"data": data, "page": 0}
        result = data["results"][0]
        text = f"🎬 **{result.get('title')}** ({result.get('year')}) · {result.get('type')}\n⭐ {result.get('rating','N/A')}/10\n📺 {len(result.get('episodes',[]))} episodes\n\nChoose episode:"
        await status.edit_text(text, reply_markup=build_movie_keyboard(data, 0))
        return
    await status.edit_text(f"No movie found for **{query}**.")

@client.on_message(filters.command(["adult", "xxx", "nsfw"], PREFIXES) & ~filters.private)
@register
@handle_error
async def adult_cmd(_, message: Message):
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

@client.on_callback_query(filters.regex(r"^mvpage\|"))
@handle_error
async def page_callback(_, callback: CallbackQuery):
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

    status = await callback.message.reply_text(f"⬇️ Downloading **{title}** S{season}E{episode} ({quality})...")
    filename = f"{title.replace(' ','_')}_s{season}e{episode}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)

    if not local_path:
        await status.edit_text(f"❌ Download failed.\nReason: {info}")
        return

    size = os.path.getsize(local_path) / (1024*1024)
    await status.edit_text(f"✅ Downloaded ({size:.1f} MB)\n▶️ Playing in Voice Chat...")

    success, msg = await play_local_file(chat_id, local_path, f"{title} S{season}E{episode}")
    if success:
        await status.edit_text(f"✅ Downloaded + Playing!\n📁 {os.path.basename(local_path)}\n📦 {size:.1f} MB\n\n{msg}")
    else:
        await status.edit_text(f"✅ Downloaded ({size:.1f} MB)\n❌ Play failed: {msg}")

@client.on_callback_query(filters.regex(r"^ad\|"))
@handle_error
async def adult_callback(_, callback: CallbackQuery):
    parts = callback.data.split("|")
    if len(parts) < 3:
        await callback.answer("Invalid")
        return
    _, page_str, idx_str = parts
    idx = int(idx_str)
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
    status = await callback.message.reply_text(f"⬇️ Downloading:\n**{title[:60]}**\nQuality: {quality}")

    filename = f"adult_{idx}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)

    if not local_path:
        await status.edit_text(f"❌ Download failed.\nReason: {info}")
        return

    size = os.path.getsize(local_path) / (1024*1024)
    await status.edit_text(f"✅ Downloaded ({size:.1f} MB)\n▶️ Playing in Voice Chat...")

    success, msg = await play_local_file(chat_id, local_path, title[:40])
    if success:
        await status.edit_text(f"✅ Downloaded + Playing!\n📁 {os.path.basename(local_path)}\n📦 {size:.1f} MB\n\n{msg}")
    else:
        await status.edit_text(f"✅ Downloaded ({size:.1f} MB)\n❌ Play failed: {msg}")

print("Music + Movie + Adult + VC Play (original stack) loaded")
if __name__ == "__main__":
    client.run()
