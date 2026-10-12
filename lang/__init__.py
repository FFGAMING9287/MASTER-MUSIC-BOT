"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

import json
import os

lang_dir = os.path.dirname(__file__)

def load_lang(code="en"):
    path = os.path.join(lang_dir, f"{code}.json")
    if not os.path.exists(path):
        path = os.path.join(lang_dir, "en.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Alias for compatibility with core/decorators.py
load = load_lang
