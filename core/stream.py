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
        # Only try the main import path
        from pytgcalls import PyTgCalls
        print("Imported PyTgCalls from pytgcalls")

        # Try MediaStream from different possible locations
        try:
            from pytgcalls.types.stream import MediaStream as MS
            _MediaStream = MS
            print("MediaStream from types.stream")
        except ImportError:
            try:
                from pytgcalls.types import MediaStream as MS
                _MediaStream = MS
                print("MediaStream from types")
            except ImportError:
                # Last resort - some versions use different name
                try:
                    from pytgcalls import MediaStream as MS
                    _MediaStream = MS
                except ImportError:
                    _init_error = "MediaStream not found. pytgcalls version may be incompatible."
                    return False

        session = getattr(config, "SESSION", None) or ""
        if not session or len(str(session).strip()) < 40:
            _init_error = (
                "SESSION variable is empty or invalid.\n"
                "Generate a new session string and add it in Railway Variables as SESSION."
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
        print("PyTgCalls object created successfully")
        return True

    except ImportError as e:
        _init_error = f"ImportError: {e}\nThe installed pytgcalls package is missing required classes."
        print(_init_error)
        return False
    except Exception as e:
        _init_error = f"{type(e).__name__}: {e}"
        print(f"PyTgCalls init error: {_init_error}")
        return False

async def play_local_file(chat_id: int, file_path: str, title: str = "Video"):
    if not os.path.exists(file_path):
        return False, "File not found on server"

    if not _lazy_init():
        return False, _init_error or "PyTgCalls failed to start."

    try:
        if not _app.is_connected:
            await _app.start()

        stream = _MediaStream(file_path)

        try:
            await _pytgcalls.play(chat_id, stream)
        except AttributeError:
            # Fallback for older API
            await _pytgcalls.join_group_call(chat_id, stream)

        return True, f"Now playing **{title}** in Voice Chat"

    except Exception as e:
        err = str(e).lower()
        print(f"play error: {e}")

        if "no active group call" in err or "not in a call" in err:
            return False, "No active Voice Chat. Start a Voice Chat in the group first."
        if "session" in err or "auth key" in err or "unauthorized" in err:
            return False, "SESSION is invalid or expired. Generate a new one."
        if "flood" in err:
            return False, "Flood wait from Telegram. Try again later."

        return False, f"Play error: {str(e)[:200]}"

# Compatibility
pytgcalls = None
app = None

async def start_stream(song, lang=None):
    pass
