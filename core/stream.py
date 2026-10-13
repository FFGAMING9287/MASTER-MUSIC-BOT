"""
Stream helper for playing local files in Voice Chat
Uses modern py-tgcalls package
"""

import os
from config import config
from pyrogram import Client

_pytgcalls = None
_app = None
_init_error = None

def _lazy_init():
    global _pytgcalls, _app, _init_error

    if _pytgcalls is not None:
        return True
    if _init_error:
        return False

    try:
        from pytgcalls import PyTgCalls
        print("PyTgCalls imported successfully")

        session = getattr(config, "SESSION", None) or ""
        if not session or len(str(session).strip()) < 40:
            _init_error = "SESSION is empty/invalid. Add a valid session string in Railway Variables."
            return False

        _app = Client(
            "MusicPlayerUB",
            api_id=int(config.API_ID),
            api_hash=str(config.API_HASH),
            session_string=str(session).strip(),
            in_memory=True,
        )
        _pytgcalls = PyTgCalls(_app)
        print("PyTgCalls instance created")
        return True

    except ImportError as e:
        _init_error = f"ImportError: {e}"
        print(_init_error)
        return False
    except Exception as e:
        _init_error = f"{type(e).__name__}: {e}"
        print(f"Init error: {_init_error}")
        return False

async def play_local_file(chat_id: int, file_path: str, title: str = "Video"):
    if not os.path.exists(file_path):
        return False, "File not found"

    if not _lazy_init():
        return False, _init_error or "PyTgCalls failed"

    try:
        if not _app.is_connected:
            await _app.start()

        # Modern py-tgcalls play method accepts file path directly
        await _pytgcalls.play(chat_id, file_path)

        return True, f"Now playing **{title}** in Voice Chat"

    except Exception as e:
        err = str(e).lower()
        print(f"play error: {e}")

        if "no active group call" in err or "not in a call" in err or "no group call" in err:
            return False, "No active Voice Chat. Start a Voice Chat in the group first."
        if "session" in err or "auth" in err or "unauthorized" in err:
            return False, "SESSION invalid/expired. Generate a new one."
        if "flood" in err:
            return False, "Flood wait. Try later."

        return False, f"Play error: {str(e)[:200]}"

pytgcalls = None
app = None

async def start_stream(song, lang=None):
    pass
