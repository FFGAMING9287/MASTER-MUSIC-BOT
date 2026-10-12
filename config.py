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

from dotenv import load_dotenv

load_dotenv()


def _positive_int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


class Config:
    def __init__(self) -> None:
        self.API_ID: str = os.environ.get("API_ID", None)
        self.API_HASH: str = os.environ.get("API_HASH", None)
        self.SESSION: str = os.environ.get("SESSION", None)
        self.BOT_TOKEN: str = os.environ.get("BOT_TOKEN", None)
        self.SUDOERS: list = [
            int(id) for id in os.environ.get("SUDOERS", " ").split() if id.isnumeric()
        ]
        if not self.SESSION or not self.API_ID or not self.API_HASH:
            print("ERROR: SESSION, API_ID and API_HASH is required!")
            quit(0)
        self.SPOTIFY: bool = False
        self.QUALITY: str = os.environ.get("QUALITY", "high").lower()
        self.PREFIXES: list = os.environ.get("PREFIX", "!").split()
        self.LANGUAGE: str = os.environ.get("LANGUAGE", "en").lower()
        self.STREAM_MODE: str = (
            "audio"
            if (os.environ.get("STREAM_MODE", "audio").lower() == "audio")
            else "video"
        )
        self.ADMINS_ONLY: bool = os.environ.get("ADMINS_ONLY", False)
        self.MOVIE_DOWNLOAD_DIR: str = os.environ.get(
            "MOVIE_DOWNLOAD_DIR", "/tmp/master-music-bot/movies"
        )
        self.MOVIE_ALLOWED_DOWNLOAD_HOSTS: set = {
            "movie-downloader-api.vercel.app",
            "bcdnw.hakunaymatata.com",
        }
        self.MOVIE_ALLOWED_DOWNLOAD_HOSTS.update(
            host.strip().lower().rstrip(".")
            for host in os.environ.get("MOVIE_ALLOWED_DOWNLOAD_HOSTS", "").split(",")
            if host.strip()
        )
        self.MOVIE_MAX_DOWNLOAD_MB: int = _positive_int_env(
            "MOVIE_MAX_DOWNLOAD_MB", 2048
        )
        self.MOVIE_CACHE_TTL_HOURS: int = _positive_int_env("MOVIE_CACHE_TTL_HOURS", 24)
        self.MOVIE_MAX_CONCURRENT_DOWNLOADS: int = _positive_int_env(
            "MOVIE_MAX_CONCURRENT_DOWNLOADS", 2
        )
        self.SPOTIFY_CLIENT_ID: str = os.environ.get("SPOTIFY_CLIENT_ID", None)
        self.SPOTIFY_CLIENT_SECRET: str = os.environ.get("SPOTIFY_CLIENT_SECRET", None)


config = Config()
