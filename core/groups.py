"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

groups = {}

def get_group(chat_id):
    if chat_id not in groups:
        set_default(chat_id)
    return groups[chat_id]

def set_group(chat_id, **kwargs):
    if chat_id not in groups:
        set_default(chat_id)
    groups[chat_id].update(kwargs)

def set_default(chat_id):
    groups[chat_id] = {
        "is_playing": False,
        "now_playing": None,
        "stream_mode": "audio",
        "lang": "en",
        "admins_only": False,
        "loop": False,
        "queue": [],
    }

def all_groups():
    return list(groups.keys())

def clear_queue(chat_id):
    if chat_id in groups:
        groups[chat_id]["queue"] = []
