"""
Music Player, Telegram Voice Chat Bot
Copyright (c) 2026-present ˹ꜰꜰɢᴀᴍɪɴɢ ̽ ᴍᴜꜱɪᴄ ʙᴏᴛ !!
"""

import time
from lang import load
from config import config
from datetime import datetime
from traceback import format_exc
from pyrogram import Client, enums
from pyrogram.types import Message
from typing import Union, Callable
from pyrogram.errors import UserAlreadyParticipant
from core.groups import get_group, all_groups, set_default

# Delayed / safe imports to avoid circular and version issues
def _get_pytgcalls():
    try:
        from pytgcalls import PyTgCalls
        return PyTgCalls
    except ImportError:
        try:
            from pytgcalls.pytgcalls import PyTgCalls
            return PyTgCalls
        except ImportError:
            return None

def register(func: Callable) -> Callable:
    async def decorator(client: Client, message: Message, *args):
        if message.chat.id not in all_groups():
            set_default(message.chat.id)
        return await func(client, message, *args)
    return decorator

def language(func: Callable) -> Callable:
    async def decorator(client, obj: Union[Message, int], *args):
        try:
            if isinstance(obj, int):
                chat_id = obj
            elif isinstance(obj, Message):
                chat_id = obj.chat.id
            else:
                chat_id = getattr(obj, "chat_id", None)
            group_lang = get_group(chat_id)["lang"]
        except BaseException:
            group_lang = getattr(config, "LANGUAGE", "en")
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
        elif message.from_user and message.from_user.id in getattr(config, "SUDOERS", []):
            return await func(client, message, *args)
        elif message.sender_chat and message.sender_chat.id == message.chat.id:
            return await func(client, message, *args)
    return decorator

def handle_error(func: Callable) -> Callable:
    async def decorator(client, obj, *args):
        pyro_client = client
        if hasattr(client, "_app"):
            try:
                pyro_client = client._app._bind_client._app
            except Exception:
                pass

        if isinstance(obj, int):
            chat_id = obj
        elif isinstance(obj, Message):
            chat_id = obj.chat.id
        else:
            chat_id = getattr(obj, "chat_id", 0)

        try:
            me = await pyro_client.get_me()
            if not hasattr(config, "SUDOERS"):
                config.SUDOERS = []
            if me.id not in config.SUDOERS:
                config.SUDOERS.append(me.id)
        except Exception:
            pass

        try:
            lang = get_group(chat_id).get("lang", "en")
        except Exception:
            lang = "en"

        try:
            return await func(client, obj, *args)
        except Exception:
            try:
                id_ = int(time.time())
                date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                chat = await pyro_client.get_chat(chat_id)
                error_msg = await pyro_client.send_message(
                    chat_id, load(lang).get("errorMessage", "An error occurred")
                )
                if config.SUDOERS:
                    await pyro_client.send_message(
                        config.SUDOERS[0],
                        f"-------- START CRASH LOG --------\n\nID: {id_}\nChat: {chat.id}\nDate: {date}\nTraceback:\n{format_exc()}\n\n-------- END CRASH LOG --------",
                        disable_web_page_preview=True,
                    )
            except Exception:
                pass
    return decorator
