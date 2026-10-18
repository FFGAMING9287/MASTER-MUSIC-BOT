"""
Movie handlers for /movie and /play integration
"""

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from movie_api import search_movie, download_movie
from core.decorators import language, register, handle_error
from config import config
import asyncio

# Store search results temporarily (chat_id -> results)
movie_cache = {}

async def build_movie_keyboard(results_data, page=0):
    """Build inline keyboard from movie search results."""
    if not results_data or not results_data.get("results"):
        return None

    result = results_data["results"][0]  # Take first result for now
    episodes = result.get("episodes", [])
    buttons = []

    # Show first 8 episode options
    for ep in episodes[:8]:
        for q in ep.get("qualities", [])[:2]:  # max 2 qualities per episode
            label = f"{result['title']} S{ep.get('season',1)}E{ep['episode']} {ep.get('language','')} {q['quality']}"
            # Callback data limited to 64 bytes
            cb_data = f"mv|{result.get('id','')}|{ep.get('season',1)}|{ep['episode']}|{ep.get('language','ja')}|{q['quality']}"
            buttons.append([InlineKeyboardButton(label[:60], callback_data=cb_data[:64])])

    if len(episodes) > 8:
        buttons.append([InlineKeyboardButton("Next →", callback_data="mv_next")])

    buttons.append([
        InlineKeyboardButton("Language: All", callback_data="mv_lang"),
        InlineKeyboardButton("Quality: All", callback_data="mv_qual")
    ])
    return InlineKeyboardMarkup(buttons)

@Client.on_message(filters.command(["movie", "mv"], config.PREFIXES) & ~filters.private)
@register
@language
@handle_error
async def movie_search(client: Client, message: Message, lang):
    query = " ".join(message.command[1:])
    if not query:
        await message.reply_text("Usage: /movie <name>")
        return

    status = await message.reply_text("🔍 Searching movies...")
    data = await search_movie(query)

    if not data or not data.get("results"):
        await status.edit_text("No results found.")
        return

    movie_cache[message.chat.id] = data
    result = data["results"][0]

    text = f"🎬 **Movie Search Results**\n\n"
    text += f"1. **{result.get('title')}** ({result.get('year')}) · {result.get('type')}\n"
    text += f"⭐ {result.get('rating', 'N/A')}/10\n"
    text += f"🌐 {result.get('country', '')}\n"
    text += f"📺 {len(result.get('episodes', []))} episodes\n\n"
    text += "Choose an available episode link below:"

    keyboard = await build_movie_keyboard(data)
    await status.edit_text(text, reply_markup=keyboard)

@Client.on_callback_query(filters.regex(r"^mv\|"))
@handle_error
async def movie_callback(client: Client, callback: CallbackQuery):
    data = callback.data.split("|")
    if len(data) < 6:
        await callback.answer("Invalid data")
        return

    _, movie_id, season, episode, language, quality = data
    await callback.answer(f"Downloading S{season}E{episode} {quality}...")

    # Find the download URL from cache
    chat_id = callback.message.chat.id
    cached = movie_cache.get(chat_id)
    if not cached:
        await callback.message.reply_text("Search expired. Please search again.")
        return

    download_url = None
    filename = f"movie_s{season}e{episode}_{quality}.mp4"
    for res in cached.get("results", []):
        for ep in res.get("episodes", []):
            if str(ep.get("episode")) == episode and str(ep.get("season",1)) == season:
                for q in ep.get("qualities", []):
                    if q.get("quality") == quality and ep.get("language", "").lower() == language.lower():
                        download_url = q.get("download_url") or q.get("downloadUrl")
                        break

    if not download_url:
        await callback.message.reply_text("Download link not found.")
        return

    status_msg = await callback.message.reply_text(
        "⬇️ Downloading… rate limits are handled with a short, bounded backoff."
    )

    local_path, detail = await download_movie(download_url, filename)

    if local_path:
        await status_msg.edit_text(f"✅ Downloaded successfully: {filename}")
        await callback.message.reply_text(f"File ready: {local_path}\nSource: {detail}")
    else:
        await status_msg.edit_text(f"❌ Download failed.\n\n{detail or 'Unknown download error'}")
