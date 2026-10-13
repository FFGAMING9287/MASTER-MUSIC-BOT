"""
Music Player + Movie Bot
"""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import os
from config import config
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters
from core.decorators import register, handle_error
from core.groups import get_group, set_group, set_default
from movie_api import search_movie, download_movie

try:
    from core.stream import app, pytgcalls, start_stream
except Exception:
    app = None
    pytgcalls = None
    async def start_stream(*a, **k): pass

movie_cache = {}

def extract_args(text):
    parts = text.split(None, 1)
    return parts[1] if len(parts) > 1 else ""

if getattr(config, "BOT_TOKEN", None):
    bot = Client("MusicPlayer", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN, in_memory=True)
    client = bot
else:
    client = app or Client("MusicPlayer", api_id=config.API_ID, api_hash=config.API_HASH, in_memory=True)

PREFIXES = getattr(config, "PREFIXES", ["!", "/", "."])

def build_movie_keyboard(data, page=0):
    if not data or not data.get("results"):
        return None
    result = data["results"][0]
    episodes = result.get("episodes", [])
    buttons = []
    start = page * 8
    end = start + 8
    slice_eps = episodes[start:end]

    for ep in slice_eps:
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

    buttons.append([
        InlineKeyboardButton("🌐 Language", callback_data="mvinfo|lang"),
        InlineKeyboardButton("📺 Quality", callback_data="mvinfo|qual")
    ])
    return InlineKeyboardMarkup(buttons)

@client.on_message(filters.command(["start"], PREFIXES) & ~filters.bot)
@handle_error
async def start(_, message: Message):
    name = message.from_user.mention if message.from_user else "User"
    await message.reply_text(f"Hello {name}!\n\n**FFGAMING X MUSIC BOT**\n\n/play <name>\n/movie <name>\n/help")

@client.on_message(filters.command("help", PREFIXES) & ~filters.bot)
@handle_error
async def help_cmd(_, message: Message):
    await message.reply_text("**Commands**\n/play <name> - Search movie/song\n/movie <name> - Movie search\n/ping\n/start")

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
    status = await message.reply_text("🔍 Searching...")
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
        text = f"🎬 **{result.get('title')}** ({result.get('year')}) · {result.get('type')}\n⭐ {result.get('rating','N/A')}/10\n📺 {len(result.get('episodes',[]))} episodes\n\nChoose episode to play:"
        await status.edit_text(text, reply_markup=build_movie_keyboard(data, 0))
        return
    await status.edit_text(f"No movie found for **{query}**. Music search coming soon.")

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
    text = f"🎬 **{result.get('title')}** ({result.get('year')}) · {result.get('type')}\n⭐ {result.get('rating','N/A')}/10\n📺 {len(result.get('episodes',[]))} episodes\n\nPage {page+1}"
    await callback.message.edit_text(text, reply_markup=build_movie_keyboard(data, page))
    await callback.answer()

@client.on_callback_query(filters.regex(r"^mvinfo\|"))
@handle_error
async def info_callback(_, callback: CallbackQuery):
    kind = callback.data.split("|")[1]
    if kind == "lang":
        await callback.answer("Language filter coming soon. Currently shows all languages.", show_alert=True)
    else:
        await callback.answer("Quality filter coming soon. Currently shows available qualities.", show_alert=True)

@client.on_callback_query(filters.regex(r"^mv\|"))
@handle_error
async def movie_callback(_, callback: CallbackQuery):
    parts = callback.data.split("|")
    if len(parts) < 6:
        await callback.answer("Invalid")
        return
    _, mid, season, episode, short_lang, quality = parts
    await callback.answer(f"Downloading S{season}E{episode} {quality}...")

    chat_id = callback.message.chat.id
    cached = movie_cache.get(chat_id)
    if not cached:
        await callback.message.reply_text("Search expired. Search again.")
        return
    data = cached["data"]

    download_url = None
    title = "Unknown"
    matched_lang = short_lang

    for res in data.get("results", []):
        title = res.get("title", "Unknown")
        for ep in res.get("episodes", []):
            if str(ep.get("episode")) == str(episode) and str(ep.get("season",1)) == str(season):
                for q in ep.get("qualities", []):
                    if q.get("quality") == quality:
                        download_url = q.get("download_url") or q.get("downloadUrl")
                        matched_lang = ep.get("language", short_lang)
                        break
                if download_url:
                    break
        if download_url:
            break

    if not download_url:
        await callback.message.reply_text("❌ Link not found. Search again.")
        return

    status = await callback.message.reply_text(
        f"⬇️ Downloading **{title}** S{season}E{episode} ({matched_lang} {quality})...\nThis can take 1-3 min."
    )

    filename = f"{title.replace(' ','_')}_s{season}e{episode}_{quality}.mp4"
    local_path, info = await download_movie(download_url, filename)

    if local_path:
        size = os.path.getsize(local_path) / (1024*1024)
        await status.edit_text(
            f"✅ Downloaded!\n📁 `{os.path.basename(local_path)}`\n📦 {size:.1f} MB\n\nJoin VC – auto-play coming next."
        )
    else:
        await status.edit_text(
            f"❌ Download failed.\n\nReason: {info}\n\n"
            "The CDN is currently rate-limiting. Wait a minute and try another quality/episode."
        )

print("Movie bot loaded")
if __name__ == "__main__":
    client.run()
