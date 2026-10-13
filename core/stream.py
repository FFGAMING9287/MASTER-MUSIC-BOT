"""
Stream helper for playing local files in Voice Chat
"""

import os
from config import config
from pyrogram import Client

_pytgcalls = None
_app = None
_MediaStream = None
_init_error = None

def _lazy_init():
    global _pytgcalls, _app, _MediaStream, _init_error

    if _pytgcalls is not None:
        return True
    if _init_error:
        return False

    try:
        try:
            from pytgcalls import PyTgCalls
        except ImportError:
            from pytgcalls.pytgcalls import PyTgCalls

        try:
            from pytgcalls.types.stream import MediaStream as MS
            _MediaStream = MS
        except ImportError:
            try:
                from pytgcalls.types import MediaStream as MS
                _MediaStream = MS
            except ImportError:
                _init_error = "MediaStream class not found in installed pytgcalls"
                return False

        session = getattr(config, "SESSION", None) or ""
        if not session or len(str(session).strip()) < 40:
            _init_error = (
                "SESSION variable is empty or invalid.\n"
                "1. Generate a new session string\n"
                "2. Add it in Railway → Variables → SESSION"
            )
            return False

        _app = Client(
            "MusicPlayerUB",
            api_id=int(config.API_ID),
            api_hash=str(config.API_HASH),
            session_string=str(session).strip(),
            in_memory=True,
        )
        _pytgcalls = PyTgCalls(_app)
        print("PyTgCalls initialized OK")
        return True

    except Exception as e:
        _init_error = f"{type(e).__name__}: {e}"
        print(f"PyTgCalls init error: {_init_error}")
        return False

async def play_local_file(chat_id: int, file_path: str, title: str = "Video"):
    if not os.path.exists(file_path):
        return False, "File not found on server"

    if not _lazy_init():
        return False, _init_error or "PyTgCalls failed to start. Check SESSION."

    try:
        if not _app.is_connected:
            await _app.start()

        stream = _MediaStream(file_path)

        try:
            await _pytgcalls.play(chat_id, stream)
        except AttributeError:
            await _pytgcalls.join_group_call(chat_id, stream)

        return True, f"Now playing **{title}** in Voice Chat"

    except Exception as e:
        err = str(e).lower()
        print(f"play error: {e}")

        if "no active group call" in err or "not in a call" in err:
            return False, "No active Voice Chat. Start a Voice Chat in the group first."
        if "session" in err or "auth key" in err or "unauthorized" in err:
            return False, "SESSION is invalid/expired. Generate a new session string."
        if "flood" in err:
            return False, "Flood wait from Telegram. Try again later."

        return False, f"Play error: {str(e)[:200]}"

# Compatibility exports
pytgcalls = None
app = None

async def start_stream(song, lang=None):
    pass
