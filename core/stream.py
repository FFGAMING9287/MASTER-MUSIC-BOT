"""
Stream helper for playing local files in Voice Chat
"""

import os
from config import config
from pyrogram import Client

PyTgCalls = None
MediaStream = None

try:
    from pytgcalls import PyTgCalls
except ImportError:
    try:
        from pytgcalls.pytgcalls import PyTgCalls
    except ImportError:
        pass

try:
    from pytgcalls.types.stream import MediaStream
except ImportError:
    try:
        from pytgcalls.types import MediaStream
    except ImportError:
        pass

# Userbot client for joining VC (needs SESSION)
app = Client(
    "MusicPlayerUB",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=getattr(config, "SESSION", None) or "",
    in_memory=True,
)

pytgcalls = None
if PyTgCalls is not None:
    try:
        pytgcalls = PyTgCalls(app)
    except Exception as e:
        print(f"PyTgCalls init error: {e}")

async def play_local_file(chat_id: int, file_path: str, title: str = "Video") -> tuple[bool, str]:
    """
    Play a local video/audio file in the group's Voice Chat.
    Returns (success, message)
    """
    if not os.path.exists(file_path):
        return False, "File not found on server"

    if pytgcalls is None or MediaStream is None:
        return False, "PyTgCalls not available. Check SESSION and requirements."

    try:
        # Join the call if needed and play
        stream = MediaStream(file_path)

        # Different versions have slightly different APIs
        try:
            await pytgcalls.play(chat_id, stream)
        except AttributeError:
            # Older style
            await pytgcalls.join_group_call(chat_id, stream)

        return True, f"Playing **{title}** in Voice Chat"
    except Exception as e:
        err = str(e)
        print(f"play_local_file error: {err}")
        if "not in a call" in err.lower() or "no active" in err.lower():
            return False, "Please start a Voice Chat in the group first, then try again."
        if "session" in err.lower() or "auth" in err.lower():
            return False, "Userbot SESSION is missing or invalid. Add SESSION in Railway variables."
        return False, f"Play error: {err[:150]}"

async def start_stream(song, lang=None):
    """Compatibility placeholder"""
    pass
