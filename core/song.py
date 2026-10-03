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

import json
import asyncio
from shlex import quote
from subprocess import PIPE
from datetime import timedelta
from aiohttp import ClientSession
from pyrogram.types import User, Message
from typing import Dict, Tuple, Union, Optional


class Song:
    def __init__(self, link: Union[str, dict], request_msg: Message) -> None:
        if isinstance(link, str):
            self.title: str = None
            self.duration: str = None
            self.thumb: str = None
            self.remote: str = None
            self.source: str = link
            self.headers: dict = None
            self.request_msg: Message = request_msg
            self.requested_by: User = request_msg.from_user
            self.parsed: bool = False
            self._retries: int = 0
        elif isinstance(link, dict):
            self.parsed: bool = True
            self._retries: int = 0
            self.duration: str = "N/A"
            self.headers: dict = None
            self.thumb: str = "https://telegra.ph/file/820cac7cb7b1a025542e2.jpg"
            for key, value in link.items():
                setattr(self, key, value)
            self.request_msg: Message = request_msg
            self.requested_by: User = request_msg.from_user

    async def parse(self) -> Tuple[bool, str]:
        if self.parsed:
            return (True, "ALREADY_PARSED")
        if self._retries >= 5:
            return (False, "MAX_RETRY_LIMIT_REACHED")
        
        try:
            from core.groups import get_group
            
            # Check karte hain ki group mein audio chalna hai ya video
            group = get_group(self.request_msg.chat.id)
            stream_mode = group.get("stream_mode", "audio")
            
            session = ClientSession()
            api_url = "http://172.104.38.31/download"
            
            # Mode ke hisaab se API ka data set karo
            if stream_mode == "video":
                params = {
                    "type": "video",
                    "quality": "720", # 720p sabse stable rahega VC ke liye
                    "url": self.source
                }
            else:
                params = {
                    "type": "audio",
                    "format": "opus",
                    "url": self.source
                }
                
            response = await session.get(api_url, params=params, timeout=60)
            data = await response.json()
            await session.close()
            
            if data.get("status") == "success":
                self.title = self._escape(data.get("title", "Unknown Title"))
                self.duration = str(timedelta(seconds=data.get("duration_sec", 0)))
                self.thumb = data.get("thumbnail", "https://telegra.ph/file/820cac7cb7b1a025542e2.jpg")
                self.remote = data.get("stream_url")
                self.headers = None
                self.parsed = True
                return (True, "PARSED")
            else:
                self._retries += 1
                return await self.parse()
        except BaseException:
            self._retries += 1
            return await self.parse()
            
    @staticmethod
    async def check_remote_url(
        path: str, headers: Optional[Dict[str, str]] = None
    ) -> bool:
        try:
            session = ClientSession()
            response = await session.get(path, timeout=5, headers=headers)
            response.close()
            await session.close()
            if response.status == 200:
                return True
            else:
                return False
        except BaseException:
            return False

    @staticmethod
    def _escape(_title: str) -> str:
        title = _title
        f = ["**", "__", "`", "~~", "--"]
        for i in f:
            title = title.replace(i, f"\\{i}")
        return title

    def to_dict(self) -> Dict[str, str]:
        return {"title": self.title, "source": self.source}
