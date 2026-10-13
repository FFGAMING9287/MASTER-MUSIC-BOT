"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
With Movie Integration
"""

import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import os
import json
from config import config
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram import Client, filters
from core.decorators import language, register, only_admins, handle_error
from core.groups import get_group, set_group, all_groups, set_default, clear_queue
from movie_api import search_movie, download_movie

# Safe stream imports
try:
    from core.stream import app, pytgcalls, ytdl, start_stream
except Exception as e:
    print(f"Stream import warning: {e}")
    app = None
    pytgcalls = None
    ytdl = None
    async def start_stream(*args, **kwargs):
        pass

# Temporary cache for movie results
movie_cache = {}

# Placeholders
async def is_sudo(message):
    return True

async def is_admin(message):
    return True

def extract_args(text):
    parts = text.split(None, 1)
    return parts[1] if len(parts) > 1 else ""

async def delete_messages(messages):
    for m in messages:
        try:
            await m.delete()
        except:
            pass


REPO = """
🤖 **Music Player + Movie**

- Repo: [GitHub](https://github.com/FFGAMING9287/MASTER-MUSIC-BOT)
- Commands: /play, /movie, /start, /help, /ping
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

PREFIXES = getattr(config, "PREFIXES", ["!", "/", "."])


def build_movie_keyboard(data, page=0):
    """Build inline keyboard from movie search results."""
    if not data or not data.get("results"):
        return None

    result = data["results"][0]
    episodes = result.get("episodes", [])
    buttons = []

    # Show up to 8 episode+quality combinations
    count = 0
    for ep in episodes:
        if count >= 8:
            break
        for q in ep.get("qualities", [])[:2]:
            if count >= 8:
                break
            label = f"▶ {result.get('title','')} S{ep.get('season',1)}E{ep['episode']} {ep.get('language','')} {q['quality']}"
            cb_data = f"mv|{result.get('id','x')}|{ep.get('season',1)}|{ep['episode']}|{ep.get('language','ja')}|{q['quality']}"
            buttons.append([InlineKeyboardButton(label[:60], callback_data=cb_data[:64])])
            count += 1

    if len(episodes) > 4:
        buttons.append([InlineKeyboardButton("Next →", callback_data="mv_next")])

    buttons.append([
        InlineKeyboardButton("🌐 Language: All", callback_data="mv_lang"),
        InlineKeyboardButton("📺 Quality: All", callback_data="mv_qual")
    ])
    return InlineKeyboardMarkup(buttons)


@client.on_message(filters.command("repo", PREFIXES) & ~filters.bot)
@handle_error
async def repo(_, message: Message):
    await message.reply_text(REPO, disable_web_page_preview=True)


@client.on_message(filters.command("ping", PREFIXES) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await message.reply_text("🤖 **Pong!**")


@client.on_message(filters.command(["start"], PREFIXES) & ~filters.bot)
@handle_error
async def start(_, message: Message):
    name = message.from_user.mention if message.from_user else "User"
    text = f"Hello {name}!\n\nWelcome to **FFGAMING X MUSIC BOT**\n\nCommands:\n• /play <song or movie name>\n• /movie <movie/series name>\n• /help\n• /ping"
    await message.reply_text(text)


@client.on_message(filters.command("help", PREFIXES) & ~filters.bot)
@handle_error
async def help_cmd(_, message: Message):
    text = """**Available Commands**

🎵 **Music / Movie**
• `/play <name>` - Search & play song or movie
• `/movie <name>` - Search movies/series only

⚙️ **Other**
• `/start` - Start the bot
• `/ping` - Check bot status
• `/repo` - Source code
"""
    await message.reply_text(text)


@client.on_message(filters.command(["movie", "mv"], PREFIXES) & ~filters.private)
@register
@handle_error
async def movie_search_cmd(_, message: Message):
    query = extract_args(message.text)
    if not query:
        await message.reply_text("Usage: `/movie <name>`\nExample: `/movie overflow`")
        return

    status = await message.reply_text("🔍 Searching movies...")
    data = await search_movie(query)

    if not data or not data.get("results"):
        await status.edit_text("❌ No results found.")
        return

    movie_cache[message.chat.id] = data
    result = data["results"][0]

    text = f"🎬 **Movie Search Results**\n\n"
    text += f"**1. {result.get('title')}** ({result.get('year')}) · {result.get('type')}\n"
    text += f"⭐ {result.get('rating', 'N/A')}/10\n"
    text += f"🌐 {result.get('country', '')}\n"
    text += f"📺 {len(result.get('episodes', []))} episodes · {len(result.get('seasons', [1]))} season(s)\n\n"
    text += "Choose an available episode link below:"

    keyboard = build_movie_keyboard(data)
    await status.edit_text(text, reply_markup=keyboard)


@client.on_message(filters.command(["p", "play"], PREFIXES) & ~filters.private)
@register
@handle_error
async def play_cmd(_, message: Message):
    query = extract_args(message.text)
    if not query:
        await message.reply_text("Usage: `/play <song or movie name>`")
        return

    status = await message.reply_text("🔍 Searching...")

    # First try movie search
    data = await search_movie(query)

    if data and data.get("results"):
        movie_cache[message.chat.id] = data
        result = data["results"][0]

        text = f"🎬 **Found Movie/Series**\n\n"
        text += f"**{result.get('title')}** ({result.get('year')}) · {result.get('type')}\n"
        text += f"⭐ {result.get('rating', 'N/A')}/10\n"
        text += f"🌐 {result.get('country', '')}\n"
        text += f"📺 {len(result.get('episodes', []))} episodes\n\n"
        text += "Choose an episode to play in VC:"

        keyboard = build_movie_keyboard(data)
        await status.edit_text(text, reply_markup=keyboard)
        return

    # Fallback message (music search will be restored later)
    await status.edit_text(
        f"🔍 No movie found for **{query}**.\n\n"
        "Music search is being restored. For now use `/movie <name>` for movies."
    )


@client.on_callback_query(filters.regex(r"^mv\|"))
@handle_error
async def movie_callback(_, callback: CallbackQuery):
    data_parts = callback.data.split("|")
    if len(data_parts) < 6:
        await callback.answer("Invalid data")
        return

    _, movie_id, season, episode, language, quality = data_parts
    await callback.answer(f"Downloading S{season}E{episode} {quality}...")

    chat_id = callback.message.chat.id
    cached = movie_cache.get(chat_id)
    if not cached:
        await callback.message.reply_text("Search expired. Please search again with /movie or /play.")
        return

    download_url = None
    title = "Unknown"
    for res in cached.get("results", []):
        title = res.get("title", "Unknown")
        for ep in res.get("episodes", []):
            if str(ep.get("episode")) == episode and str(ep.get("season", 1)) == season:
                if ep.get("language", "").lower() == language.lower() or language == "ja":
                    for q in ep.get("qualities", []):
                        if q.get("quality") == quality:
                            download_url = q.get("download_url") or q.get("downloadUrl")
                            break
                if download_url:
                    break
        if download_url:
            break

    if not download_url:
        await callback.message.reply_text("❌ Download link not found.")
        return

    status_msg = await callback.message.reply_text(
        f"⬇️ **Downloading in background...**\n\n"
        f"{title} S{season}E{episode} ({quality})\nPlease wait..."
    )

    filename = f"{title.replace(' ', '_')}_s{season}e{episode}_{quality}.mp4"
    local_path = await download_movie(download_url, filename)

    if local_path:
        await status_msg.edit_text(
            f"✅ **Downloaded successfully!**\n\n"
            f"📁 `{filename}`\n\n"
            f"Now join a Voice Chat and the bot will play it (VC play integration next)."
        )
    else:
        await status_msg.edit_text("❌ Download failed. Please try another quality.")


print("Music Player + Movie integration loaded successfully")

if __name__ == "__main__":
    client.run()
