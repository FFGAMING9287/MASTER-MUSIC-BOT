"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

groups = {}

def get_group(chat_id):
    return groups.get(chat_id, {"admins_only": False})

def set_group(chat_id, data):
    groups[chat_id] = data

def all_groups():
    return list(groups.keys())
