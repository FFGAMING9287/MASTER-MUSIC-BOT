"""
Stream helper - inject missing exception so py-tgcalls can load
"""

import os
import sys
from config import config
from pyrogram import Client

# === Fix for missing GroupCallForbidden ===
try:
    from pyrogram.errors import GroupCallForbidden
except ImportError:
    # Create a dummy exception so py-tgcalls can import
    class GroupCallForbidden(Exception):
        pass

    # Inject it into pyrogram.errors
    import pyrogram.errors
    pyrogram.errors.GroupCallForbidden = GroupCallForbidden
    sys.modules["pyrogram.errors"].GroupCallForbidden = GroupCallForbidden
# ==========================================

_pytgcalls = None
_app = None
_init_error = "VC play not available"

def _lazy_init():
    global _pytgcalls, _app, _init_error

    if _pytgcalls is not None:
        return True

    try:
        from pytgcalls import PyTgCalls
    except Exception as e:
        _init_error = f"PyTgCalls import failed: {e}"
        return False

    session = getattr(config, "SESSION", None) or ""
    if not session or len(str(session).strip()) < 40:
        _init_error = "SESSION missing or invalid"
        return False

    try:
        _app = Client(
            "MusicPlayerUB",
            api_id=int(config.API_ID),
            api_hash=str(config.API_HASH),
            session_string=str(session).strip(),
            in_memory=True,
        )
        _pytgcalls = PyTgCalls(_app)
        print("PyTgCalls initialized with dummy GroupCallForbidden")
        return True
    except Exception as e:
        _init_error = f"{type(e).__name__}: {e}"
        return False

async def play_local_file(chat_id: int, file_path: str, title: str = "Video"):
    if not os.path.exists(file_path):
        return False, "File not found"

    if not _lazy_init():
        return False, f"Auto-play unavailable.\n({_init_error})\n\nFile is still downloaded."

    try:
        if not _app.is_connected:
            await _app.start()

        try:
            await _pytgcalls.play(chat_id, file_path)
        except Exception:
            try:
                from pytgcalls.types import MediaStream
                await _pytgcalls.play(chat_id, MediaStream(file_path))
            except Exception:
                await _pytgcalls.join_group_call(chat_id, file_path)

        return True, f"Now playing **{title}** in Voice Chat"

    except Exception as e:
        err = str(e).lower()
        if "no active" in err or "group call" in err:
            return False, "No active Voice Chat. Start one first."
        if "session" in err or "auth" in err:
            return False, "SESSION invalid"
        return False, f"Play failed: {str(e)[:150]}"

pytgcalls = None
app = None

async def start_stream(song, lang=None):
    pass
