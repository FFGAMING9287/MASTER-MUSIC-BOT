"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ꭙ ᴍᴜꜱɪᴄ ʙᴏᴛ !!

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>
"""

import os

from pyrogram import Client
from pyrogram.raw.functions.phone import CreateGroupCall
from pyrogram.raw.types import InputPeerChannel
from pytgcalls import PyTgCalls
from pytgcalls.exceptions import NoActiveGroupCall
from pytgcalls.types import AudioQuality, VideoQuality
from pytgcalls.types.stream import MediaStream
from yt_dlp import YoutubeDL

from config import config
from core.funcs import generate_cover
from core.groups import get_group, set_title
from core.song import Song

safone = {}
ydl_opts = {
    "quiet": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
}
app = Client(
    "MusicPlayerUB",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=config.SESSION,
    in_memory=True,
)
ytdl = YoutubeDL(ydl_opts)
pytgcalls = PyTgCalls(app)


async def start_stream(song: Song, lang, *, create_if_missing: bool = True):
    chat = song.request_msg.chat
    if safone.get(chat.id) is not None:
        try:
            await safone[chat.id].delete()
        except BaseException:
            pass
    infomsg = await song.request_msg.reply_text(lang["downloading"])
    try:
        await pytgcalls.play(
            chat.id,
            get_quality(song),
        )
    except NoActiveGroupCall:
        if not create_if_missing:
            raise
        peer = await app.resolve_peer(chat.id)
        await app.invoke(
            CreateGroupCall(
                peer=InputPeerChannel(
                    channel_id=peer.channel_id,
                    access_hash=peer.access_hash,
                ),
                random_id=app.rnd_id() // 9000000000,
            )
        )
        return await start_stream(song, lang, create_if_missing=create_if_missing)
    await set_title(chat.id, song.title, client=app)
    thumb = await generate_cover(
        song.title,
        chat.title,
        chat.id,
        song.thumb,
    )
    safone[chat.id] = await song.request_msg.reply_photo(
        photo=thumb,
        caption=lang["playing"]
        % (
            song.title,
            song.source,
            song.duration,
            song.request_msg.chat.id,
            (
                song.requested_by.mention
                if song.requested_by
                else song.request_msg.sender_chat.title
            ),
        ),
        quote=False,
    )
    await infomsg.delete()
    if os.path.exists(thumb):
        os.remove(thumb)


def get_quality(song: Song) -> MediaStream:
    group = get_group(song.request_msg.chat.id)
    stream_mode = getattr(song, "stream_mode", None) or group["stream_mode"]
    if stream_mode == "video":
        movie_quality = str(getattr(song, "movie_quality", ""))
        digits = "".join(
            character for character in movie_quality if character.isdigit()
        )
        if digits:
            resolution = int(digits)
            if resolution <= 480:
                video_quality = VideoQuality.SD_480p
            elif resolution <= 720:
                video_quality = VideoQuality.HD_720p
            else:
                video_quality = VideoQuality.FHD_1080p
        elif config.QUALITY.lower() == "medium":
            video_quality = VideoQuality.HD_720p
        elif config.QUALITY.lower() == "low":
            video_quality = VideoQuality.SD_480p
        else:
            video_quality = VideoQuality.FHD_1080p
        if config.QUALITY.lower() == "high":
            return MediaStream(
                song.remote,
                AudioQuality.HIGH,
                video_quality,
                headers=song.headers,
            )
        elif config.QUALITY.lower() == "medium":
            return MediaStream(
                song.remote,
                AudioQuality.MEDIUM,
                video_quality,
                headers=song.headers,
            )
        elif config.QUALITY.lower() == "low":
            return MediaStream(
                song.remote,
                AudioQuality.LOW,
                video_quality,
                headers=song.headers,
            )
        else:
            print("WARNING: Invalid Quality Specified. Defaulting to High!")
            return MediaStream(
                song.remote,
                AudioQuality.HIGH,
                video_quality,
                headers=song.headers,
            )
    else:
        if config.QUALITY.lower() == "high":
            return MediaStream(
                song.remote,
                AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
                headers=song.headers,
            )
        elif config.QUALITY.lower() == "medium":
            return MediaStream(
                song.remote,
                AudioQuality.MEDIUM,
                video_flags=MediaStream.Flags.IGNORE,
                headers=song.headers,
            )
        elif config.QUALITY.lower() == "low":
            return MediaStream(
                song.remote,
                AudioQuality.LOW,
                video_flags=MediaStream.Flags.IGNORE,
                headers=song.headers,
            )
        else:
            print("WARNING: Invalid Quality Specified. Defaulting to High!")
            return MediaStream(
                song.remote,
                AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
                headers=song.headers,
            )
