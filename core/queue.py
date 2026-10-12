"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

queues = {}

def get_queue(chat_id):
    return queues.get(chat_id, [])

def clear_queue(chat_id):
    if chat_id in queues:
        queues[chat_id] = []

def shuffle_queue(chat_id):
    import random
    if chat_id in queues:
        random.shuffle(queues[chat_id])
