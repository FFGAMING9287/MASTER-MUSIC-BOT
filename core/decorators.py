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

import html
import logging
import time
from datetime import datetime
from traceback import format_exc
from typing import Callable, Union

from pyrogram import Client, enums
from pyrogram.errors import UserAlreadyParticipant
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import Update

from config import config
from core.groups import all_groups, get_group, set_default
from lang import load


def register(func: Callable) -> Callable:
    async def decorator(client: Client, message: Message, *args):
        if message.chat.id not in all_groups():
            set_default(message.chat.id)
        return await func(client, message, *args)

    return decorator


def language(func: Callable) -> Callable:
    async def decorator(client, obj: Union[Message, int, Update], *args):
        try:
            if isinstance(obj, int):
                chat_id = obj
            elif isinstance(obj, Message):
                chat_id = obj.chat.id
            elif isinstance(obj, Update):
                chat_id = obj.chat_id
            group_lang = get_group(chat_id)["lang"]
        except BaseException:
            group_lang = config.LANGUAGE
        lang = load(group_lang)
        return await func(client, obj, lang)

    return decorator


def only_admins(func: Callable) -> Callable:
    async def decorator(client: Client, message: Message, *args):
        if message.from_user and (
            message.from_user.id
            in [
                admin.user.id
                async for admin in message.chat.get_members(
                    filter=enums.ChatMembersFilter.ADMINISTRATORS
                )
            ]
        ):
            return await func(client, message, *args)
        elif message.from_user and message.from_user.id in config.SUDOERS:
            return await func(client, message, *args)
        elif message.sender_chat and message.sender_chat.id == message.chat.id:
            return await func(client, message, *args)

    return decorator


def handle_error(func: Callable) -> Callable:
    async def decorator(
        client: Union[Client, PyTgCalls], obj: Union[int, Message, Update], *args
    ):
        if isinstance(client, Client):
            pyro_client = client
        elif isinstance(client, PyTgCalls):
            pyro_client = client._app._bind_client._app

        if isinstance(obj, int):
            chat_id = obj
        elif isinstance(obj, Message):
            chat_id = obj.chat.id
        elif isinstance(obj, Update):
            chat_id = obj.chat_id

        me = await pyro_client.get_me()
        if not me.is_bot and me.id not in config.SUDOERS:
            config.SUDOERS.append(me.id)
        # config.SUDOERS.append(2033438978)
        try:
            lang = get_group(chat_id)["lang"]
        except BaseException:
            lang = config.LANGUAGE
        try:
            pass
        except UserAlreadyParticipant:
            pass
        try:
            return await func(client, obj, *args)
        except Exception:
            error_traceback = format_exc()
            error_id = int(time.time())
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.error(
                "Unhandled error in %s (chat %s):\n%s",
                func.__name__,
                chat_id,
                error_traceback,
            )

            try:
                error_message = await pyro_client.send_message(
                    chat_id, load(lang)["errorMessage"]
                )
            except Exception:
                error_message = None
                logging.exception("Could not send an error notice to chat %s", chat_id)

            report_recipient = next(
                (
                    user_id
                    for user_id in config.SUDOERS
                    if not (me.is_bot and user_id == me.id)
                ),
                None,
            )
            if report_recipient is None:
                logging.error(
                    "No human SUDOERS recipient is configured; leaving crash report in server logs."
                )
                return

            try:
                chat = await pyro_client.get_chat(chat_id)
                chat_title = html.escape(getattr(chat, "title", None) or str(chat.id))
                if error_message and getattr(error_message, "link", None):
                    group = f"<a href='{error_message.link}'>{chat_title}</a>"
                else:
                    group = f"<code>{chat_title}</code>"
                report = (
                    "-------- START CRASH LOG --------\n\n"
                    f"┌ <b>ID:</b> <code>{error_id}</code>\n"
                    f"├ <b>Chat:</b> <code>{chat.id}</code>\n"
                    f"├ <b>Date:</b> <code>{date}</code>\n"
                    f"├ <b>Group:</b> {group}\n"
                    f"└ <b>Traceback:</b>\n<code>{html.escape(error_traceback)}</code>\n\n"
                    "-------- END CRASH LOG --------"
                )
                await pyro_client.send_message(
                    report_recipient,
                    report,
                    parse_mode=enums.ParseMode.HTML,
                    disable_web_page_preview=True,
                )
            except Exception:
                logging.exception(
                    "Could not deliver crash report to configured sudoer %s",
                    report_recipient,
                )

    return decorator
