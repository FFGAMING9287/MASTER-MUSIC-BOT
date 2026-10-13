"""
Stream helper - fully defensive for any pytgcalls / pyrogram version
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
        # Try multiple import styles
        PyTgCalls = None
        try:
            from pytgcalls import PyTgCalls as PTC
            PyTgCalls = PTC
        except ImportError:
            try:
                from py_tgcalls import PyTgCalls as PTC
                PyTgCalls = PTC
            except ImportError:
                _init_error = "Could not import PyTgCalls from pytgcalls or py_tgcalls"
                return False

        session = getattr(config, "SESSION", None) or ""
        if not session or len(str(session).strip()) < 40:
            _init_error = "SESSION is empty or invalid. Add a valid long session string in Railway Variables."
            return False

        _app = Client(
            "MusicPlayerUB",
            api_id=int(config.API_ID),
            api_hash=str(config.API_HASH),
            session_string=str(session).strip(),
            in_memory=True,
        )
        _pytgcalls = PyTgCalls(_app)
        print("PyTgCalls ready")
        return True

    except Exception as e:
        # Catch any import-time errors from the library itself (like missing GroupCallForbidden)
        _init_error = f"{type(e).__name__}: {e}"
        print(f"Init failed: {_init_error}")
        return False

async def play_local_file(chat_id: int, file_path: str, title: str = "Video"):
    if not os.path.exists(file_path):
        return False, "File not found on disk"

    if not _lazy_init():
        return False, (
            f"VC engine failed to start:\n{_init_error}\n\n"
            "Possible fixes:\n"
            "1. Make sure SESSION is set correctly\n"
            "2. Redeploy after requirements change\n"
            "3. The py-tgcalls package may need a different pyrogram version"
        )

    try:
        if not _app.is_connected:
            await _app.start()

        # Try different play signatures
        try:
            await _pytgcalls.play(chat_id, file_path)
        except TypeError:
            # Some versions need MediaStream wrapper
            try:
                from pytgcalls.types import MediaStream
                await _pytgcalls.play(chat_id, MediaStream(file_path))
            except Exception:
                await _pytgcalls.join_group_call(chat_id, file_path)

        return True, f"Now playing **{title}** in Voice Chat"

    except Exception as e:
        err = str(e).lower()
        print(f"Play error: {e}")

        if any(x in err for x in ["no active", "not in a call", "no group call", "group call not found"]):
            return False, "No active Voice Chat. Please start a Voice Chat / Video Chat in the group first."
        if any(x in err for x in ["session", "auth key", "unauthorized", "auth_key"]):
            return False, "SESSION is invalid or expired. Generate a new session string."
        if "flood" in err:
            return False, "Telegram flood wait. Wait a few minutes."
        if "groupcallforbidden" in err or "forbidden" in err:
            return False, "Bot/userbot is not allowed to join this Voice Chat (admin rights needed)."

        return False, f"Play error: {str(e)[:220]}"

pytgcalls = None
app = None

async def start_stream(song, lang=None):
    pass
