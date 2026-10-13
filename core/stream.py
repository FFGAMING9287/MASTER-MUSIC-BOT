"""
Stream helper based on original MusicPlayer working code
Uses py-tgcalls 2.2.10 + PyrogramMod
"""

import os
from config import config
from pyrogram import Client
from yt_dlp import YoutubeDL
from pytgcalls import PyTgCalls
from pytgcalls.types.stream import MediaStream
from pytgcalls.types import AudioQuality, VideoQuality
from pytgcalls.exceptions import NoActiveGroupCall
from pyrogram.raw.types import InputPeerChannel
from pyrogram.raw.functions.phone import CreateGroupCall

ydl_opts = {
    "quiet": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
}

app = Client(
    "MusicPlayerUB",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=getattr(config, "SESSION", "") or "",
    in_memory=True,
)
ytdl = YoutubeDL(ydl_opts)
pytgcalls = PyTgCalls(app)


async def play_local_file(chat_id: int, file_path: str, title: str = "Video"):
    """Play a local downloaded file in Voice Chat (original style)."""
    if not os.path.exists(file_path):
        return False, "File not found"

    try:
        stream = MediaStream(
            file_path,
            AudioQuality.HIGH,
            VideoQuality.HD_720p,
        )
        await pytgcalls.play(chat_id, stream)
        return True, f"Now playing **{title}** in Voice Chat"
    except NoActiveGroupCall:
        # Try to create the group call
        try:
            peer = await app.resolve_peer(chat_id)
            await app.invoke(
                CreateGroupCall(
                    peer=InputPeerChannel(
                        channel_id=peer.channel_id,
                        access_hash=peer.access_hash,
                    ),
                    random_id=app.rnd_id() // 9000000000,
                )
            )
            # Retry play
            stream = MediaStream(
                file_path,
                AudioQuality.HIGH,
                VideoQuality.HD_720p,
            )
            await pytgcalls.play(chat_id, stream)
            return True, f"Created VC + now playing **{title}**"
        except Exception as e2:
            return False, f"No active Voice Chat and could not create one: {e2}"
    except Exception as e:
        err = str(e).lower()
        if "session" in err or "auth" in err:
            return False, "SESSION invalid or missing"
        return False, f"Play error: {str(e)[:180]}"


async def start_stream(song, lang=None):
    """Compatibility placeholder"""
    pass
