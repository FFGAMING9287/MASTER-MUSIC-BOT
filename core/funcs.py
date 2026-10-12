"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

from pyrogram import Client
from config import config

app = Client("MusicPlayer", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN) if hasattr(config, "BOT_TOKEN") else None

async def search(message):
    # Search logic from clean zip
    return None

async def ytdl(url):
    # yt-dlp logic
    pass

async def safone(query):
    pass

def check_yt_url(url):
    return "youtube" in url or "youtu.be" in url

def extract_args(message):
    return message.text.split(None, 1)[1] if len(message.command) > 1 else ""

async def delete_messages(messages):
    for m in messages:
        try:
            await m.delete()
        except:
            pass

async def get_spotify_playlist(url):
    return []

async def get_youtube_playlist(url):
    return []

def set_title(chat_id, title):
    pass
