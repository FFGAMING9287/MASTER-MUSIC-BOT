"""
Music Player — Yoru-style player UI with colored buttons (FFGAMING)
"""

import asyncio

asyncio.set_event_loop(asyncio.new_event_loop())
import os
import re
import tempfile
import time
from urllib.parse import urlsplit

from pyrogram import Client, StopPropagation, filters
from pyrogram.types import (
    CallbackQuery,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from config import config
from core.buttons import (
    delete_message_styled,
    edit_message_media_styled,
    edit_message_styled,
    player_keyboard_api,
    progress_button_text,
    queue_keyboard_api,
    send_message_styled,
    send_photo_styled,
    send_sticker_from_set,
)
from core.decorators import handle_error, register
from core.duration import duration_from_file, duration_from_item
from core.progress import cancel_progress, on_pause, on_resume, start_progress
from core.rich_ui import (
    clean_name,
    html_error,
    html_help,
    html_info,
    html_mode,
    html_ping,
    html_queue,
    html_start,
    plain_now_playing,
    send_rich,
    status_downloading,
    status_results,
    status_searching,
)
from core.settings_store import (
    DEFAULT_API_URLS,
    delete_cookie,
    delete_custom_api,
    get_api_url,
    get_api_urls,
    get_custom_apis,
    has_cookie,
    set_api_url,
    set_api_urls,
    set_cookie,
    set_custom_api,
    validate_https_url,
)
from core.stream import (
    get_queue_text,
    get_state,
    pause_stream,
    play_local_file,
    play_remote_url,
    resume_stream,
    seek_stream,
    skip_stream,
    stop_stream,
)
from core.youtube import (
    INVIDIOUS_INSTANCES,
    PIPED_INSTANCES,
    get_stream_info,
    search_youtube,
)
from movie_api import (
    download_file,
    get_movie_box_downloads,
    movie_box_proxy_url,
    search_adult,
    search_movie,
    search_movie_box,
)

movie_cache = {}
movie_box_cache = {}
adult_cache = {}
yt_cache = {}
BOT_PUBLIC = True
STICKER_SET_NAME = "Vividbeetle2_by_fStikBot"
loading_stickers = {}
settings_pending = {}

API_SETTINGS = {
    "movie_box": ("Movie Box API", "Movie/TV search and episode downloads for /movie."),
    "legacy_movie": ("Legacy Movie API", "Existing movie provider used by /play."),
    "adult": ("Adult API", "Search and downloads for /adult."),
    "piped": (
        "Piped instances",
        "YouTube music search/stream resolution for /song and /yt.",
    ),
    "invidious": ("Invidious instances", "Fallback YouTube search/stream resolution."),
}
COOKIE_SETTINGS = {
    "movie_box": (
        "Movie Box API",
        "Cookie header sent only to the configured Movie Box API host.",
    ),
    "legacy_movie": (
        "Legacy Movie API",
        "Cookie header sent only to the configured legacy API host.",
    ),
    "adult": ("Adult API", "Cookie header sent only to the configured adult API host."),
    "youtube": ("YouTube", "Netscape cookies used by the yt-dlp fallback."),
}


def extract_args(text):
    parts = text.split(None, 1)
    return parts[1] if len(parts) > 1 else ""


def is_owner(user_id: int) -> bool:
    owner_id = int(getattr(config, "OWNER_ID", 0) or 0)
    sudo = getattr(config, "SUDO_USERS", []) or []
    return (bool(owner_id) and user_id == owner_id) or user_id in sudo


def can_use(user_id: int) -> bool:
    if BOT_PUBLIC:
        return True
    return is_owner(user_id)


def fmt_duration(sec):
    if not sec:
        return "00:00"
    try:
        sec = int(sec)
    except Exception:
        return "00:00"
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def requester_name(user):
    if not user:
        return "User"
    if user.username:
        return f"@{user.username}"
    name = (user.first_name or "") + ((" " + user.last_name) if user.last_name else "")
    return clean_name(name) or "User"


def build_player_keyboard(paused=False, queue_len=0, autoplay=False, duration=0, pos=0):
    ap = "ON" if autoplay else "OFF"
    pause_label = "▶ Resume" if paused else "Ⅱ Pause"
    pause_action = "ctl|resume" if paused else "ctl|pause"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    progress_button_text(duration, pos), callback_data="ctl|noop"
                )
            ],
            [
                InlineKeyboardButton("↻ Replay", callback_data="ctl|replay"),
                InlineKeyboardButton(pause_label, callback_data=pause_action),
                InlineKeyboardButton("⏭ Skip", callback_data="ctl|skip"),
            ],
            [
                InlineKeyboardButton(
                    f"☰ Queue · {queue_len}", callback_data="ctl|queue"
                ),
                InlineKeyboardButton("⏹ End Queue", callback_data="ctl|stop"),
            ],
            [InlineKeyboardButton(f"Autoplay: {ap}", callback_data="ctl|autoplay")],
        ]
    )


def build_queue_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("▶ Play Now", callback_data="ctl|playnow"),
                InlineKeyboardButton("⏭ Skip", callback_data="ctl|skip"),
            ],
            [InlineKeyboardButton("⏹ End Queue", callback_data="ctl|stop")],
        ]
    )


def start_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🎵 Song", callback_data="help|song"),
                InlineKeyboardButton("🎬 Movie", callback_data="help|movie"),
                InlineKeyboardButton("🔞 Adult", callback_data="help|adult"),
            ],
            [
                InlineKeyboardButton("⏯ Controls", callback_data="help|ctrl"),
                InlineKeyboardButton("📖 Help", callback_data="help|full"),
            ],
        ]
    )


def _display_api_url(url):
    parts = urlsplit(url or "")
    if not parts.hostname:
        return "not configured"
    host = parts.hostname
    if parts.port:
        host = f"{host}:{parts.port}"
    return f"{parts.scheme}://{host}{parts.path}"[:110]


def _api_values(key):
    if key == "piped":
        return get_api_urls(key, PIPED_INSTANCES)
    if key == "invidious":
        return get_api_urls(key, INVIDIOUS_INSTANCES)
    return [get_api_url(key, DEFAULT_API_URLS.get(key, ""))]


def settings_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("API endpoints", callback_data="settings|apis"),
                InlineKeyboardButton("Cookies", callback_data="settings|cookies"),
            ]
        ]
    )


def settings_api_text():
    lines = [
        "⚙️ API settings",
        "Each API’s use is listed above its endpoint. Built-in entries update live bot providers.",
    ]
    for key, (label, purpose) in API_SETTINGS.items():
        current = _api_values(key)
        lines.append(f"\n{label} — {purpose}")
        lines.extend(f"  {_display_api_url(url)}" for url in current[:3])
        if len(current) > 3:
            lines.append(f"  +{len(current) - 3} more")
    custom = get_custom_apis()
    lines.append(
        "\nCustom API entries are saved with a use label; they need a command adapter before a bot command can call them."
    )
    for name, item in sorted(custom.items()):
        lines.append(f"\n{name} — {item['purpose']}\n  {_display_api_url(item['url'])}")
    return "\n".join(lines)[:3900]


def settings_api_keyboard():
    rows = []
    builtin_keys = list(API_SETTINGS)
    for index in range(0, len(builtin_keys), 2):
        row = [
            InlineKeyboardButton(
                f"Edit {API_SETTINGS[key][0]}", callback_data=f"settings|api|{key}"
            )
            for key in builtin_keys[index : index + 2]
        ]
        rows.append(row)
    rows.append(
        [InlineKeyboardButton("＋ Add custom API", callback_data="settings|addapi")]
    )
    for name in sorted(get_custom_apis())[:8]:
        rows.append(
            [
                InlineKeyboardButton(
                    f"Edit {name}"[:32], callback_data=f"settings|customedit|{name}"
                ),
                InlineKeyboardButton(
                    "Delete", callback_data=f"settings|customdel|{name}"
                ),
            ]
        )
    rows.append([InlineKeyboardButton("← Settings", callback_data="settings|menu")])
    return InlineKeyboardMarkup(rows)


def settings_cookie_text():
    lines = [
        "🔐 Cookie settings",
        "Cookies are encrypted at rest and never displayed here. Use /settings in a private chat only.",
        "API cookies go only to that configured API host. YouTube Netscape cookies are used by the yt-dlp fallback.",
    ]
    for key, (label, purpose) in COOKIE_SETTINGS.items():
        status = "configured" if has_cookie(key) else "not set"
        lines.append(f"\n{label} — {purpose}\n  Status: {status}")
    return "\n".join(lines)


def settings_cookie_keyboard():
    rows = []
    for key, (label, _) in COOKIE_SETTINGS.items():
        status = "✅" if has_cookie(key) else "＋"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{status} {label}", callback_data=f"settings|cookie|{key}"
                ),
                InlineKeyboardButton(
                    "Delete", callback_data=f"settings|delcookie|{key}"
                ),
            ]
        )
    rows.append([InlineKeyboardButton("← Settings", callback_data="settings|menu")])
    return InlineKeyboardMarkup(rows)


async def reply_rich_or_text(message, html, plain, reply_markup=None):
    ok = await send_rich(message.chat.id, html, reply_markup=None)
    if ok:
        return True
    await message.reply_text(plain, reply_markup=reply_markup)
    return False


async def send_now_playing(
    chat_id, title, duration=0, requester="User", queued=False, thumb="", edit_msg=None
):
    state = get_state(chat_id)
    qlen = len(state.get("queue") or [])
    ap = bool(state.get("autoplay"))
    if duration:
        state["duration"] = int(duration)
    plain = plain_now_playing(
        title, duration, requester, queued, qlen, pos=0, autoplay=ap
    )
    kb_api = (
        queue_keyboard_api()
        if queued
        else player_keyboard_api(
            paused=False, autoplay=ap, duration=duration, queue_len=qlen
        )
    )
    kb = (
        build_queue_keyboard()
        if queued
        else build_player_keyboard(
            paused=False, queue_len=qlen, autoplay=ap, duration=duration
        )
    )
    result = None
    msg = None
    media = False
    message_id = getattr(edit_msg, "id", None)

    # Reuse the search/download status message as the final artwork card.
    if edit_msg and thumb:
        result = await edit_message_media_styled(
            chat_id, message_id, thumb, plain, reply_markup=kb_api
        )
        if result:
            media = True
            if isinstance(result, dict):
                message_id = result.get("message_id", message_id)

    if result is None and thumb and not edit_msg:
        result = await send_photo_styled(chat_id, thumb, plain, reply_markup=kb_api)
        if result:
            media = True
            if isinstance(result, dict):
                message_id = result.get("message_id")

    # Use the active Pyrogram client if the Bot API photo request is unavailable.
    if result is None and thumb:
        try:
            if edit_msg:
                msg = await edit_msg.edit_media(
                    InputMediaPhoto(media=thumb, caption=plain, parse_mode="html"),
                    reply_markup=kb,
                )
            else:
                msg = await client.send_photo(
                    chat_id,
                    photo=thumb,
                    caption=plain,
                    reply_markup=kb,
                    parse_mode="html",
                )
            media = True
            message_id = msg.id
        except Exception as exc:
            print(f"player photo fallback failed: {exc}")

    if result is None and msg is None and edit_msg:
        edited = await edit_message_styled(
            chat_id, message_id, text=plain, reply_markup=kb_api
        )
        if edited:
            message_id = edit_msg.id
            msg = edit_msg
        else:
            try:
                msg = await edit_msg.edit_text(
                    plain, reply_markup=kb, parse_mode="html"
                )
                message_id = msg.id
            except Exception as exc:
                print(f"player text edit fallback failed: {exc}")

    if result is None and msg is None and not edit_msg:
        result = await send_message_styled(chat_id, plain, reply_markup=kb_api)
        if result:
            if isinstance(result, dict):
                message_id = result.get("message_id")
        else:
            try:
                msg = await client.send_message(
                    chat_id,
                    plain,
                    reply_markup=kb,
                    parse_mode="html",
                    disable_web_page_preview=True,
                )
                message_id = msg.id
            except Exception as exc:
                print(f"send_now_playing fail: {exc}")
                return False

    # The photo/text fallback sends a new message only when in-place editing failed.
    if edit_msg and message_id and message_id != edit_msg.id:
        try:
            await edit_msg.delete()
        except Exception:
            pass

    if not message_id:
        return False

    class _Msg:
        pass

    progress_msg = msg
    if progress_msg is None:
        progress_msg = _Msg()
        progress_msg.id = message_id
    if not queued and duration and duration > 0:
        state["np_media"] = media
        await start_progress(
            client, chat_id, progress_msg, title, duration, requester, get_state
        )
    return True


async def play_yt_result(chat_id, info):
    title = (info.get("title") or "YouTube")[:60]
    if info.get("is_local") or (
        info.get("path") and os.path.isfile(info.get("path", ""))
    ):
        path = info.get("path") or info.get("url")
        return await play_local_file(chat_id, path, title)
    return await play_remote_url(chat_id, info["url"], title)


if getattr(config, "BOT_TOKEN", None):
    bot = Client(
        "MusicPlayer",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
        in_memory=True,
    )
    client = bot
else:
    from core.stream import app

    client = app


async def start_loading_sticker(chat_id):
    """Send one actual sticker from the configured pack per active chat flow."""
    if chat_id in loading_stickers:
        return loading_stickers[chat_id]
    result = await send_sticker_from_set(chat_id, STICKER_SET_NAME)
    message_id = result.get("message_id") if isinstance(result, dict) else None

    # MTProto-only deployments can still fetch the public set using Pyrogram.
    if not message_id:
        try:
            sticker_set = await client.get_sticker_set(STICKER_SET_NAME)
            sticker = next(iter(getattr(sticker_set, "stickers", []) or []), None)
            if sticker:
                sent = await client.send_sticker(chat_id, sticker.file_id)
                message_id = getattr(sent, "id", None)
        except Exception as exc:
            print(f"Sticker pack send fallback failed: {type(exc).__name__}: {exc}")

    if message_id:
        loading_stickers[chat_id] = message_id
    else:
        print("Could not send sticker from the configured public sticker set.")
    return message_id


async def clear_loading_sticker(chat_id):
    message_id = loading_stickers.pop(chat_id, None)
    if not message_id:
        return
    deleted = await delete_message_styled(chat_id, message_id)
    if not deleted:
        try:
            await client.delete_messages(chat_id, message_id)
        except Exception:
            pass


PREFIXES = getattr(config, "PREFIXES", ["!", "/", "."])


def _is_private_chat(chat):
    kind = getattr(chat, "type", "")
    return str(getattr(kind, "value", kind)).lower() == "private"


async def _ask_settings_input(user_id, text, state):
    prompt = await client.send_message(
        user_id, text, reply_markup=ForceReply(), parse_mode=None
    )
    state["prompt_id"] = prompt.id
    state["expires"] = time.time() + 300
    settings_pending[user_id] = state


def _settings_intro():
    return (
        "⚙️ Owner settings — private chat only.\n"
        "Built-in API endpoints update their live bot providers. Cookies and API URLs are encrypted at rest.\n"
        "Keep the bot_settings_data directory on persistent hosting storage to retain settings after redeploys."
    )


@client.on_message(
    filters.command("settings", PREFIXES) & filters.private & ~filters.bot
)
async def settings_command(_, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_owner(user_id):
        return await message.reply_text(
            "🔒 Owner only. Configure OWNER_ID or SUDO_USERS in the bot environment.",
            parse_mode=None,
        )
    await message.reply_text(
        _settings_intro(), reply_markup=settings_menu_keyboard(), parse_mode=None
    )


@client.on_message(
    filters.command("settings", PREFIXES) & ~filters.private & ~filters.bot
)
async def settings_group_command(_, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if is_owner(user_id):
        return await message.reply_text(
            "For privacy, open the bot in a private chat and send /settings there.",
            parse_mode=None,
        )
    return await message.reply_text("🔒 Owner only.", parse_mode=None)


@client.on_callback_query(filters.regex(r"^settings\|"))
async def settings_callback(_, callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else 0
    if not is_owner(user_id):
        return await callback.answer("Owner only", show_alert=True)
    if not callback.message or not _is_private_chat(callback.message.chat):
        return await callback.answer("Use settings in a private chat", show_alert=True)

    parts = callback.data.split("|")
    action = parts[1] if len(parts) > 1 else "menu"
    if action == "menu":
        await callback.message.edit_text(
            _settings_intro(), reply_markup=settings_menu_keyboard(), parse_mode=None
        )
    elif action == "apis":
        await callback.message.edit_text(
            settings_api_text(), reply_markup=settings_api_keyboard(), parse_mode=None
        )
    elif action == "cookies":
        await callback.message.edit_text(
            settings_cookie_text(),
            reply_markup=settings_cookie_keyboard(),
            parse_mode=None,
        )
    elif action == "api" and len(parts) == 3:
        key = parts[2]
        if key not in API_SETTINGS:
            return await callback.answer("Unknown API setting", show_alert=True)
        label = API_SETTINGS[key][0]
        if key in ("piped", "invidious"):
            prompt = (
                f"{label}: send comma-separated HTTPS base URLs, in preferred order. "
                "This replaces the current instance list."
            )
            kind = "api_urls"
        else:
            prompt = (
                f"{label}: send the HTTPS API base URL (include /api where required). "
                "Query strings and embedded credentials are not accepted."
            )
            kind = "api_url"
        await _ask_settings_input(user_id, prompt, {"kind": kind, "key": key})
        await callback.answer("Reply to the prompt")
    elif action == "addapi":
        await _ask_settings_input(
            user_id,
            "Add a custom API registry entry as: name | purpose/use | https://api.example/path. "
            "Custom entries are labeled and saved, but need a code adapter before a bot command can call them.",
            {"kind": "custom_add"},
        )
        await callback.answer("Reply to the prompt")
    elif action == "customedit" and len(parts) == 3:
        item = get_custom_apis().get(parts[2])
        if not item:
            return await callback.answer("Custom API not found", show_alert=True)
        await _ask_settings_input(
            user_id,
            f"Send the new HTTPS base URL for custom API {parts[2]}.",
            {"kind": "custom_url", "name": parts[2], "purpose": item["purpose"]},
        )
        await callback.answer("Reply to the prompt")
    elif action == "customdel" and len(parts) == 3:
        delete_custom_api(parts[2])
        await callback.message.edit_text(
            settings_api_text(), reply_markup=settings_api_keyboard(), parse_mode=None
        )
        await callback.answer("Custom API deleted")
    elif action == "cookie" and len(parts) == 3:
        key = parts[2]
        if key not in COOKIE_SETTINGS:
            return await callback.answer("Unknown cookie service", show_alert=True)
        if key == "youtube":
            prompt = (
                "Upload a Netscape-format YouTube cookies.txt as a .txt document, or paste its full contents. "
                "This private reply will be deleted after processing."
            )
        else:
            prompt = (
                f"Send the Cookie header for {COOKIE_SETTINGS[key][0]} as name=value; name2=value2. "
                "It is sent only to that configured API host and this private reply will be deleted."
            )
        await _ask_settings_input(user_id, prompt, {"kind": "cookie", "key": key})
        await callback.answer("Reply to the prompt")
    elif action == "delcookie" and len(parts) == 3:
        if parts[2] not in COOKIE_SETTINGS:
            return await callback.answer("Unknown cookie service", show_alert=True)
        delete_cookie(parts[2])
        await callback.message.edit_text(
            settings_cookie_text(),
            reply_markup=settings_cookie_keyboard(),
            parse_mode=None,
        )
        await callback.answer("Cookie removed")
    else:
        await callback.answer("Unknown settings action", show_alert=True)


def _validate_cookie_payload(service, value):
    value = value.strip()
    if not value or len(value.encode("utf-8")) > 100_000:
        raise ValueError("Cookie content is empty or larger than 100 KB.")
    if service == "youtube":
        lines = value.splitlines()
        has_header = any("Netscape HTTP Cookie File" in line for line in lines[:10])
        has_cookie_row = False
        for line in lines:
            row = line[len("#HttpOnly_") :] if line.startswith("#HttpOnly_") else line
            if not row.strip() or (
                row.startswith("#") and not line.startswith("#HttpOnly_")
            ):
                continue
            fields = row.split("\t")
            if len(fields) >= 7 and fields[5] and fields[6]:
                has_cookie_row = True
                break
        if not has_header or not has_cookie_row:
            raise ValueError("Use a valid Netscape-format YouTube cookies.txt file.")
        return value

    if "\n" in value or "\r" in value:
        raise ValueError("API cookies must be a single Cookie header line.")
    if value.lower().startswith("cookie:"):
        value = value.split(":", 1)[1].strip()
    pairs = [part.strip() for part in value.split(";") if part.strip()]
    if not pairs or any(
        "=" not in part or not part.split("=", 1)[0].strip() for part in pairs
    ):
        raise ValueError("Use a Cookie header like name=value; name2=value2.")
    return "; ".join(pairs)


async def _settings_input_text(message, state):
    if state["kind"] == "cookie" and state["key"] == "youtube" and message.document:
        document = message.document
        if document.file_size and document.file_size > 100_000:
            raise ValueError("Cookie file must be 100 KB or smaller.")
        if document.file_name and not document.file_name.lower().endswith(".txt"):
            raise ValueError("Upload the Netscape cookie file as a .txt document.")
        descriptor, path = tempfile.mkstemp(
            prefix="youtube-cookie-upload-", suffix=".txt"
        )
        os.close(descriptor)
        try:
            await message.download(file_name=path)
            with open(path, "r", encoding="utf-8") as cookie_file:
                return cookie_file.read()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
    return message.text or message.caption or ""


@client.on_message(filters.private & (filters.text | filters.document) & ~filters.bot)
async def settings_input_handler(_, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not is_owner(user_id):
        return
    state = settings_pending.get(user_id)
    if not state:
        return
    reply = message.reply_to_message
    if not reply or reply.id != state.get("prompt_id"):
        return
    if state.get("expires", 0) < time.time():
        settings_pending.pop(user_id, None)
        try:
            await message.delete()
        except Exception:
            pass
        await client.send_message(
            user_id, "Settings prompt expired. Send /settings again."
        )
        raise StopPropagation

    kind = state.get("kind")
    try:
        text = await _settings_input_text(message, state)
        if kind == "api_url":
            url = validate_https_url(text)
            set_api_url(state["key"], url)
            result = "✅ API endpoint saved. It applies to the next request; no restart is needed."
        elif kind == "api_urls":
            urls = [item.strip() for item in re.split(r"[,\n]+", text) if item.strip()]
            set_api_urls(state["key"], urls)
            result = "✅ API instance list saved. It applies to the next request."
        elif kind == "custom_add":
            fields = [item.strip() for item in text.split("|", 2)]
            if len(fields) != 3:
                raise ValueError(
                    "Format: name | purpose/use | https://api.example/path"
                )
            name, purpose, url = fields
            name = name.lower()
            if name in API_SETTINGS:
                raise ValueError("That name is reserved for a built-in API.")
            set_custom_api(name, purpose, url)
            result = "✅ Custom API saved with its use label. It needs a code adapter before commands can call it."
        elif kind == "custom_url":
            set_custom_api(state["name"], state["purpose"], text)
            result = "✅ Custom API URL updated in the registry."
        elif kind == "cookie":
            cookie_value = _validate_cookie_payload(state["key"], text)
            set_cookie(state["key"], cookie_value)
            result = "✅ Cookie saved encrypted. The submitted private message is being deleted."
        else:
            raise ValueError("Unknown settings prompt.")
        settings_pending.pop(user_id, None)
        try:
            await message.delete()
        except Exception:
            pass
        await client.send_message(
            user_id,
            result + "\nUse /settings to view or change settings.",
            reply_markup=settings_menu_keyboard(),
            parse_mode=None,
        )
    except ValueError as exc:
        settings_pending.pop(user_id, None)
        try:
            await message.delete()
        except Exception:
            pass
        await client.send_message(
            user_id,
            f"❌ {exc}\nOpen /settings and try again.",
            reply_markup=settings_menu_keyboard(),
            parse_mode=None,
        )
    except Exception:
        settings_pending.pop(user_id, None)
        try:
            await message.delete()
        except Exception:
            pass
        await client.send_message(
            user_id,
            "❌ Could not save settings. Check the bot's private persistent storage and retry.",
            reply_markup=settings_menu_keyboard(),
            parse_mode=None,
        )
    raise StopPropagation


def build_movie_keyboard(data, page=0):
    if not data or not data.get("results"):
        return None
    result = data["results"][0]
    episodes = result.get("episodes", [])
    buttons = []
    start = page * 8
    end = start + 8
    for ep in episodes[start:end]:
        for q in ep.get("qualities", [])[:2]:
            lang = ep.get("language", "?")
            label = f"▶ S{ep.get('season',1)}E{ep['episode']} {lang} {q['quality']}"
            short_lang = (lang or "unk")[:4].lower()
            cb = f"mv|{result.get('id','x')}|{ep.get('season',1)}|{ep['episode']}|{short_lang}|{q['quality']}"
            buttons.append([InlineKeyboardButton(label[:58], callback_data=cb[:64])])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Prev", callback_data=f"mvpage|{page-1}"))
    if end < len(episodes):
        nav.append(InlineKeyboardButton("Next →", callback_data=f"mvpage|{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons) if buttons else None


def movie_box_episodes(result):
    episodes = result.get("episodes") or []
    languages = result.get("languages") or []
    detail_path = (result.get("detailPath") or "").lower()
    available = list(
        dict.fromkeys(str(ep.get("language")) for ep in episodes if ep.get("language"))
    )
    preferred = next(
        (lang for lang in available if lang.lower() in detail_path), None
    ) or next((lang for lang in available if lang.lower() == "english"), None)
    if preferred:
        filtered = [ep for ep in episodes if ep.get("language") == preferred]
        if filtered:
            return filtered
    if episodes:
        return episodes

    language = next(
        (
            item
            for item in languages
            if str(item.get("language", "")).lower() == "english"
            and any(season.get("episodes") for season in item.get("seasons", []))
        ),
        next(
            (
                item
                for item in languages
                if any(season.get("episodes") for season in item.get("seasons", []))
            ),
            None,
        ),
    )
    flattened = []
    if language:
        for season_data in language.get("seasons", []):
            for episode_data in season_data.get("episodes", []):
                flattened.append(
                    {
                        **episode_data,
                        "season": episode_data.get(
                            "season", season_data.get("season", 1)
                        ),
                        "language": language.get("language", "English"),
                    }
                )
    return flattened


def build_movie_box_results_keyboard(cache):
    results = cache.get("results") or []
    if not results:
        return None
    page_size = 5
    page = max(0, int(cache.get("list_page", 0)))
    start = page * page_size
    end = min(start + page_size, len(results))
    buttons = []
    for idx in range(start, end):
        item = results[idx]
        kind = "📺" if str(item.get("type", "")).lower() in ("tv", "series") else "🎬"
        title = clean_name(item.get("title", "Movie"))[:35]
        year = item.get("year") or ""
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{kind} {title} {year}".strip()[:58],
                    callback_data=f"mbres|{idx}",
                )
            ]
        )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Prev", callback_data=f"mbpage|{page-1}"))
    if end < len(results):
        nav.append(InlineKeyboardButton("Next →", callback_data=f"mbpage|{page+1}"))
    elif len(results) < int(cache.get("count", len(results))):
        nav.append(
            InlineKeyboardButton(
                "More Results →", callback_data=f"mbmore|{cache.get('api_page', 1) + 1}"
            )
        )
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)


def build_movie_box_episode_keyboard(result_index, episodes, page=0):
    if not episodes:
        return None
    page_size = 8
    start = max(0, page) * page_size
    end = min(start + page_size, len(episodes))
    buttons = []
    for ep in episodes[start:end]:
        season = ep.get("season", 1)
        episode = ep.get("episode")
        if episode is None:
            continue
        label = f"▶ S{season}E{episode} {ep.get('language', '')}".strip()
        buttons.append(
            [
                InlineKeyboardButton(
                    label[:58], callback_data=f"mbep|{result_index}|{season}|{episode}"
                )
            ]
        )
    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(
                "← Prev", callback_data=f"mbepage|{result_index}|{page-1}"
            )
        )
    if end < len(episodes):
        nav.append(
            InlineKeyboardButton(
                "Next →", callback_data=f"mbepage|{result_index}|{page+1}"
            )
        )
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("← Search results", callback_data="mbback")])
    return InlineKeyboardMarkup(buttons)


def build_movie_box_quality_keyboard(options):
    buttons = []
    row = []
    for idx, option in enumerate(options[:8]):
        resolution = option.get("resolution")
        quality = option.get("quality") or (f"{resolution}p" if resolution else "MP4")
        row.append(
            InlineKeyboardButton(f"⬇ {quality}"[:30], callback_data=f"mbq|{idx}")
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("← Search results", callback_data="mbback")])
    return InlineKeyboardMarkup(buttons)


def build_adult_keyboard(items, page=0):
    buttons = []
    start = page * 6
    end = start + 6
    for i, item in enumerate(items[start:end]):
        title = (item.get("title") or "Video")[:40]
        quality = item.get("quality", "?")
        size = item.get("size", "?")
        label = f"▶ {title} [{quality}] {size}"
        cb = f"ad|{page}|{start+i}"
        buttons.append([InlineKeyboardButton(label[:58], callback_data=cb[:64])])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("← Prev", callback_data=f"adpage|{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton("Next →", callback_data=f"adpage|{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons) if buttons else None


def build_yt_keyboard(items):
    buttons = []
    for i, item in enumerate(items[:8]):
        title = (item.get("title") or "Song")[:42]
        dur = fmt_duration(item.get("duration"))
        label = f"▶ {title} [{dur}]"
        buttons.append([InlineKeyboardButton(label[:58], callback_data=f"yt|{i}")])
    return InlineKeyboardMarkup(buttons) if buttons else None


@client.on_message(filters.command(["start"], PREFIXES) & ~filters.bot)
@handle_error
async def start(_, message: Message):
    name = clean_name(message.from_user.first_name if message.from_user else "User")
    mode = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
    plain = f"🎧 **FFGAMING X MUSIC BOT**\n\n👋 Hello **{name}**!\n🔐 Mode : `{mode}`\n\n🎵 /song /yt · 🎬 /play /movie · 🔞 /adult\n⏯ /skip /pause /resume /stop /queue\n🔐 /mode public|private"
    await reply_rich_or_text(message, html_start(name, mode), plain, start_keyboard())


@client.on_message(filters.command("help", PREFIXES) & ~filters.bot)
@handle_error
async def help_cmd(_, message: Message):
    mode = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
    plain = f"📖 **Commands**\nMode: `{mode}`\n\n/song /yt · /play /movie · /adult\n/skip /pause /resume /stop /queue\n/mode public|private"
    await reply_rich_or_text(message, html_help(mode), plain, start_keyboard())


@client.on_callback_query(filters.regex(r"^help\|"))
@handle_error
async def help_callback(_, callback: CallbackQuery):
    section = callback.data.split("|")[1]
    map_html = {
        "song": html_info("🎵 YouTube Music", "<code>/song <name></code>"),
        "movie": html_info("🎬 Movies", "<code>/play <name></code>"),
        "adult": html_info("🔞 Adult", "<code>/adult <query></code>"),
        "ctrl": html_info("⏯ Controls", "▶ Ⅱ ↻ ⏭ ⏹ · Autoplay · «10s · Close"),
        "full": html_help("🌐 Public" if BOT_PUBLIC else "🔒 Private"),
    }
    plain_map = {
        "song": "🎵 **YouTube**\n`/song <name>`",
        "movie": "🎬 **Movies**\n`/play` `/movie`",
        "adult": "🔞 **Adult**\n`/adult` `/xxx`",
        "ctrl": "⏯ **Controls**",
        "full": "📖 **Help**",
    }
    html = map_html.get(section, map_html["full"])
    plain = plain_map.get(section, plain_map["full"])
    await callback.answer()
    ok = await send_rich(callback.message.chat.id, html, reply_markup=None)
    if not ok:
        try:
            await callback.message.edit_text(plain, reply_markup=start_keyboard())
        except Exception:
            await callback.message.reply_text(plain, reply_markup=start_keyboard())


@client.on_message(filters.command("ping", PREFIXES) & ~filters.bot)
@handle_error
async def ping(_, message: Message):
    await reply_rich_or_text(message, html_ping(), "🤖 **Pong!**\n✅ Bot online")


@client.on_message(filters.command("mode", PREFIXES) & ~filters.bot)
@handle_error
async def mode_cmd(_, message: Message):
    global BOT_PUBLIC
    if not is_owner(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Owner only"), "🔒 **Owner Only**"
        )
    arg = extract_args(message.text).lower().strip()
    if arg in ("public", "on", "open"):
        BOT_PUBLIC = True
        await reply_rich_or_text(
            message,
            html_mode("🌐 Public", "Everyone can use."),
            "🌐 **Public Mode ON**",
        )
    elif arg in ("private", "off", "lock"):
        BOT_PUBLIC = False
        await reply_rich_or_text(
            message, html_mode("🔒 Private", "Owner only."), "🔒 **Private Mode ON**"
        )
    else:
        status = "🌐 Public" if BOT_PUBLIC else "🔒 Private"
        await reply_rich_or_text(
            message, html_mode(status, "/mode public|private"), f"🔐 Mode: `{status}`"
        )


@client.on_message(filters.command(["skip", "next"], PREFIXES) & ~filters.private)
@handle_error
async def skip_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    cancel_progress(message.chat.id)
    ok, msg = await skip_stream(message.chat.id)
    await reply_rich_or_text(message, html_info("⏭ Skip", msg), f"⏭ {msg}")


@client.on_message(filters.command("pause", PREFIXES) & ~filters.private)
@handle_error
async def pause_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    on_pause(message.chat.id, get_state)
    ok, msg = await pause_stream(message.chat.id)
    await reply_rich_or_text(message, html_info("⏸ Pause", msg), msg)


@client.on_message(filters.command("resume", PREFIXES) & ~filters.private)
@handle_error
async def resume_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    on_resume(message.chat.id, get_state)
    ok, msg = await resume_stream(message.chat.id)
    await reply_rich_or_text(message, html_info("▶️ Resume", msg), msg)


@client.on_message(filters.command(["stop", "end"], PREFIXES) & ~filters.private)
@handle_error
async def stop_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    cancel_progress(message.chat.id)
    ok, msg = await stop_stream(message.chat.id)
    await reply_rich_or_text(
        message, html_info("⏹ Stopped", msg), f"⏹ **Stopped**\n{msg}"
    )


@client.on_message(filters.command(["queue", "q"], PREFIXES) & ~filters.private)
@handle_error
async def queue_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    body = get_queue_text(message.chat.id)
    await reply_rich_or_text(message, html_queue(body), f"☰ **Queue**\n\n{body}")


@client.on_callback_query(filters.regex(r"^ctl\|"))
@handle_error
async def control_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    action = callback.data.split("|")[1]
    chat_id = callback.message.chat.id
    state = get_state(chat_id)
    qlen = len(state.get("queue") or [])

    if action == "pause":
        on_pause(chat_id, get_state)
        ok, msg = await pause_stream(chat_id)
        await callback.answer((msg or "Paused")[:180], show_alert=not ok)
        if ok:
            await edit_message_styled(
                chat_id,
                callback.message.id,
                reply_markup=player_keyboard_api(
                    paused=True,
                    autoplay=bool(state.get("autoplay")),
                    duration=state.get("duration", 0),
                    queue_len=qlen,
                ),
            )
    elif action == "resume":
        on_resume(chat_id, get_state)
        ok, msg = await resume_stream(chat_id)
        await callback.answer((msg or "Resumed")[:180], show_alert=not ok)
        if ok:
            await edit_message_styled(
                chat_id,
                callback.message.id,
                reply_markup=player_keyboard_api(
                    paused=False,
                    autoplay=bool(state.get("autoplay")),
                    duration=state.get("duration", 0),
                    queue_len=qlen,
                ),
            )
    elif action in ("skip", "playnow"):
        cancel_progress(chat_id)
        ok, msg = await skip_stream(chat_id)
        response = "Playing queued track" if action == "playnow" else "Skipped"
        await callback.answer(response if ok else (msg or "")[:180])
        if not await send_rich(chat_id, html_info("⏭ Skip", msg)):
            await callback.message.reply_text(f"⏭ {msg}")
    elif action == "stop":
        cancel_progress(chat_id)
        ok, msg = await stop_stream(chat_id)
        await callback.answer("Stopped")
        if not await send_rich(chat_id, html_info("⏹ Stopped", msg)):
            await callback.message.reply_text(f"⏹ {msg}")
    elif action == "queue":
        await callback.answer()
        body = get_queue_text(chat_id)
        if not await send_rich(chat_id, html_queue(body)):
            await callback.message.reply_text(f"☰ **Queue**\n\n{body}")
    elif action == "replay":
        cancel_progress(chat_id)
        path = state.get("path")
        title = state.get("title") or "Track"
        if not path:
            return await callback.answer("Nothing to replay", show_alert=True)
        if os.path.isfile(str(path)):
            ok, msg = await play_local_file(chat_id, path, title, force=True)
        else:
            ok, msg = await play_remote_url(chat_id, path, title, force=True)
        await callback.answer("Replaying..." if ok else (msg or "")[:180])
        if ok:
            dur = (
                await duration_from_file(path)
                if os.path.isfile(str(path))
                else (state.get("duration") or 0)
            )
            await send_now_playing(
                chat_id, title, dur, requester_name(callback.from_user)
            )
    elif action == "autoplay":
        state["autoplay"] = not bool(state.get("autoplay"))
        ap = "ON" if state["autoplay"] else "OFF"
        await callback.answer(f"Autoplay : {ap}")
        await edit_message_styled(
            chat_id,
            callback.message.id,
            reply_markup=player_keyboard_api(
                paused=bool(state.get("paused")),
                autoplay=state["autoplay"],
                duration=state.get("duration", 0),
                queue_len=qlen,
            ),
        )
    elif action == "seekback":
        ok, msg = await seek_stream(chat_id, -10)
        await callback.answer((msg or "« -10s")[:180], show_alert=not ok)
    elif action == "seekfwd":
        ok, msg = await seek_stream(chat_id, 10)
        await callback.answer((msg or "+10s »")[:180], show_alert=not ok)
    elif action == "close":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer("Closed")
    else:
        await callback.answer()


@client.on_message(
    filters.command(["song", "yt", "music", "s"], PREFIXES) & ~filters.private
)
@register
@handle_error
async def song_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    query = extract_args(message.text)
    if not query:
        return await reply_rich_or_text(
            message,
            html_info("🎵 YouTube", "<code>/song <name></code>"),
            "🎵 `/song <name>`",
        )
    status = await message.reply_text(status_searching("YouTube"), parse_mode=None)
    await start_loading_sticker(message.chat.id)
    req = requester_name(message.from_user)
    if "youtube.com" in query or "youtu.be" in query:
        await status.edit_text(status_downloading("YouTube"), parse_mode=None)
        info = await get_stream_info(query)
        if not info:
            await clear_loading_sticker(message.chat.id)
            return await status.edit_text("❌ Could not get stream", parse_mode=None)
        ok, msg = await play_yt_result(message.chat.id, info)
        if not ok:
            await clear_loading_sticker(message.chat.id)
            return await status.edit_text(f"❌ {msg}", parse_mode=None)
        await send_now_playing(
            message.chat.id,
            info.get("title", "YouTube"),
            info.get("duration") or 0,
            req,
            "queue" in msg.lower(),
            info.get("thumb", ""),
            edit_msg=status,
        )
        await clear_loading_sticker(message.chat.id)
        return
    results = await search_youtube(query, limit=6)
    if not results:
        await clear_loading_sticker(message.chat.id)
        return await status.edit_text("❌ No results found", parse_mode=None)
    yt_cache[message.chat.id] = results
    kb = build_yt_keyboard(results)
    await status.edit_text(
        status_results("YouTube", query, len(results)), reply_markup=kb, parse_mode=None
    )


@client.on_callback_query(filters.regex(r"^yt\|"))
@handle_error
async def yt_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    idx = int(callback.data.split("|")[1])
    chat_id = callback.message.chat.id
    results = yt_cache.get(chat_id)
    if not results or idx >= len(results):
        return await callback.answer("Expired", show_alert=True)
    item = results[idx]
    await callback.answer("Loading...")
    status = await callback.message.edit_text(
        status_downloading(item["title"]),
        parse_mode=None,
    )
    await start_loading_sticker(chat_id)
    req = requester_name(callback.from_user)
    info = await get_stream_info(item["url"])
    if not info:
        await clear_loading_sticker(chat_id)
        return await status.edit_text("❌ Could not get stream", parse_mode=None)
    ok, msg = await play_yt_result(chat_id, info)
    if not ok:
        await clear_loading_sticker(chat_id)
        return await status.edit_text(f"❌ {msg}", parse_mode=None)
    dur = info.get("duration") or item.get("duration") or 0
    await send_now_playing(
        chat_id,
        info.get("title", item["title"]),
        dur,
        req,
        "queue" in msg.lower(),
        item.get("thumb", ""),
        edit_msg=status,
    )
    await clear_loading_sticker(chat_id)


@client.on_message(filters.command(["movie", "mv"], PREFIXES) & ~filters.private)
@register
@handle_error
async def movie_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    query = extract_args(message.text)
    if not query:
        return await reply_rich_or_text(
            message,
            html_info("🎬 Movies", "<code>/movie <name></code>"),
            "🎬 `/movie <name>`",
        )
    status = await message.reply_text(status_searching("movie"), parse_mode=None)
    await start_loading_sticker(message.chat.id)
    data = await search_movie_box(query, page=1, per_page=10)
    if not data or not data.get("results"):
        await clear_loading_sticker(message.chat.id)
        return await status.edit_text("❌ No results found", parse_mode=None)
    movie_box_cache[message.chat.id] = {
        "query": query,
        "api_page": 1,
        "per_page": 10,
        "count": int(data.get("count") or len(data["results"])),
        "results": data["results"],
        "list_page": 0,
        "options": None,
    }
    await status.edit_text(
        status_results("Movie", query, data.get("count", len(data["results"]))),
        reply_markup=build_movie_box_results_keyboard(movie_box_cache[message.chat.id]),
        parse_mode=None,
    )


@client.on_message(filters.command(["p", "play"], PREFIXES) & ~filters.private)
@register
@handle_error
async def play_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    query = extract_args(message.text)
    if not query:
        return await reply_rich_or_text(
            message,
            html_info("🎬 Play", "<code>/play <name></code>"),
            "🎬 `/play <name>`",
        )
    status = await message.reply_text(status_searching("movie"), parse_mode=None)
    await start_loading_sticker(message.chat.id)
    data = await search_movie(query)
    if data and data.get("results"):
        movie_cache[message.chat.id] = {"data": data, "page": 0}
        result = data["results"][0]
        kb = build_movie_keyboard(data, 0)
        await status.edit_text(
            f"🎬 {clean_name(result.get('title', 'Movie'))} · {result.get('year', '')}\n"
            f"Choose an episode below.",
            reply_markup=kb,
            parse_mode=None,
        )
        return
    await clear_loading_sticker(message.chat.id)
    await status.edit_text(f"❌ No movie.\nTry /song {query}", parse_mode=None)


@client.on_message(
    filters.command(["adult", "xxx", "nsfw"], PREFIXES) & ~filters.private
)
@register
@handle_error
async def adult_cmd(_, message: Message):
    if not can_use(message.from_user.id if message.from_user else 0):
        return await reply_rich_or_text(
            message, html_error("Private mode"), "🔒 Private mode"
        )
    query = extract_args(message.text)
    if not query:
        return await reply_rich_or_text(
            message,
            html_info("🔞 Adult", "<code>/adult <query></code>"),
            "🔞 `/adult <query>`",
        )
    status = await message.reply_text(status_searching("adult"), parse_mode=None)
    await start_loading_sticker(message.chat.id)
    data = await search_adult(query)
    if not data or not data.get("items"):
        await clear_loading_sticker(message.chat.id)
        return await status.edit_text("❌ No results found", parse_mode=None)
    items = data["items"]
    adult_cache[message.chat.id] = {"items": items, "page": 0}
    kb = build_adult_keyboard(items, 0)
    await status.edit_text(
        status_results("Adult", query, len(items)), reply_markup=kb, parse_mode=None
    )


async def show_movie_box_download_choices(
    message, chat_id, cache, result_index, season, episode
):
    result = cache["results"][result_index]
    options = await get_movie_box_downloads(
        str(result.get("id", "")),
        str(result.get("detailPath", "")),
        season=season,
        episode=episode,
    )
    options = [item for item in (options or []) if item.get("url")]
    if not options:
        return await message.edit_text(
            "❌ No downloadable streams were returned for this selection.",
            parse_mode=None,
        )
    cache["download_context"] = {
        "result_index": result_index,
        "season": season,
        "episode": episode,
        "options": options,
    }
    title = clean_name(result.get("title", "Movie"))
    label = f"{title} S{season}E{episode}" if season and episode else title
    return await message.edit_text(
        f"🎬 {label}\nChoose a quality:",
        reply_markup=build_movie_box_quality_keyboard(options),
        parse_mode=None,
    )


@client.on_callback_query(filters.regex(r"^mbpage\|"))
@handle_error
async def movie_box_page_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    cache = movie_box_cache.get(callback.message.chat.id)
    if not cache:
        return await callback.answer("Search expired")
    cache["list_page"] = max(0, int(callback.data.split("|")[1]))
    await callback.message.edit_text(
        status_results("Movie", cache["query"], cache["count"]),
        reply_markup=build_movie_box_results_keyboard(cache),
        parse_mode=None,
    )
    await callback.answer()


@client.on_callback_query(filters.regex(r"^mbmore\|"))
@handle_error
async def movie_box_more_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    chat_id = callback.message.chat.id
    cache = movie_box_cache.get(chat_id)
    if not cache:
        return await callback.answer("Search expired")
    page = int(callback.data.split("|")[1])
    await callback.answer("Loading more results...")
    data = await search_movie_box(
        cache["query"], page=page, per_page=cache.get("per_page", 10)
    )
    if not data or not data.get("results"):
        return await callback.message.edit_text(
            "❌ No more results found.", parse_mode=None
        )
    cache["results"].extend(data["results"])
    cache["api_page"] = page
    cache["count"] = int(data.get("count") or cache["count"])
    cache["list_page"] = (len(cache["results"]) - len(data["results"])) // 5 + 1
    await callback.message.edit_text(
        status_results("Movie", cache["query"], cache["count"]),
        reply_markup=build_movie_box_results_keyboard(cache),
        parse_mode=None,
    )


@client.on_callback_query(filters.regex(r"^mbback$"))
@handle_error
async def movie_box_back_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    cache = movie_box_cache.get(callback.message.chat.id)
    if not cache:
        return await callback.answer("Search expired")
    cache["download_context"] = None
    await callback.message.edit_text(
        status_results("Movie", cache["query"], cache["count"]),
        reply_markup=build_movie_box_results_keyboard(cache),
        parse_mode=None,
    )
    await callback.answer()


@client.on_callback_query(filters.regex(r"^mbres\|"))
@handle_error
async def movie_box_result_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    chat_id = callback.message.chat.id
    cache = movie_box_cache.get(chat_id)
    if not cache:
        return await callback.answer("Search expired")
    result_index = int(callback.data.split("|")[1])
    if result_index >= len(cache["results"]):
        return await callback.answer("Result expired")
    result = cache["results"][result_index]
    cache["selected_result"] = result_index
    episodes = movie_box_episodes(result)
    await callback.answer("Loading links..." if not episodes else "Choose an episode")
    if episodes:
        cache["episode_page"] = 0
        title = clean_name(result.get("title", "Movie"))
        year = result.get("year") or ""
        return await callback.message.edit_text(
            f"📺 {title} {year}\nChoose an episode:",
            reply_markup=build_movie_box_episode_keyboard(result_index, episodes),
            parse_mode=None,
        )
    return await show_movie_box_download_choices(
        callback.message, chat_id, cache, result_index, 0, 0
    )


@client.on_callback_query(filters.regex(r"^mbepage\|"))
@handle_error
async def movie_box_episode_page_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    parts = callback.data.split("|")
    result_index, page = int(parts[1]), int(parts[2])
    cache = movie_box_cache.get(callback.message.chat.id)
    if not cache or result_index >= len(cache["results"]):
        return await callback.answer("Search expired")
    episodes = movie_box_episodes(cache["results"][result_index])
    cache["episode_page"] = page
    title = clean_name(cache["results"][result_index].get("title", "Movie"))
    await callback.message.edit_text(
        f"📺 {title}\nChoose an episode:",
        reply_markup=build_movie_box_episode_keyboard(result_index, episodes, page),
        parse_mode=None,
    )
    await callback.answer()


@client.on_callback_query(filters.regex(r"^mbep\|"))
@handle_error
async def movie_box_episode_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    parts = callback.data.split("|")
    result_index, season, episode = map(int, parts[1:4])
    chat_id = callback.message.chat.id
    cache = movie_box_cache.get(chat_id)
    if not cache or result_index >= len(cache["results"]):
        return await callback.answer("Search expired")
    await callback.answer("Getting download options...")
    return await show_movie_box_download_choices(
        callback.message, chat_id, cache, result_index, season, episode
    )


@client.on_callback_query(filters.regex(r"^mbq\|"))
@handle_error
async def movie_box_quality_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    chat_id = callback.message.chat.id
    cache = movie_box_cache.get(chat_id)
    context = cache.get("download_context") if cache else None
    if not context:
        return await callback.answer("Selection expired", show_alert=True)
    option_index = int(callback.data.split("|")[1])
    options = context.get("options") or []
    if option_index >= len(options):
        return await callback.answer("Quality expired", show_alert=True)
    option = options[option_index]
    source_url = option.get("url") or option.get("downloadUrl")
    if not source_url:
        return await callback.answer("No stream URL", show_alert=True)

    result = cache["results"][context["result_index"]]
    title = clean_name(result.get("title", "Movie"))
    season, episode = context["season"], context["episode"]
    label = f"{title} S{season}E{episode}" if season and episode else title
    resolution = option.get("resolution")
    quality = option.get("quality") or (f"{resolution}p" if resolution else "MP4")
    await callback.answer("Downloading...")
    await start_loading_sticker(chat_id)
    status = await callback.message.edit_text(
        status_downloading(label, quality), parse_mode=None
    )
    filename = f"{title.replace(' ', '_')}_{season}_{episode}_{quality}.mp4"
    proxy_url = movie_box_proxy_url(source_url, filename)
    local_path, info = await download_file(proxy_url, filename)
    if not local_path:
        await clear_loading_sticker(chat_id)
        return await status.edit_text(f"❌ Download failed\n{info}", parse_mode=None)
    success, message_text = await play_local_file(chat_id, local_path, label[:60])
    if not success:
        await clear_loading_sticker(chat_id)
        return await status.edit_text(f"❌ {message_text}", parse_mode=None)
    duration = await duration_from_file(local_path)
    await send_now_playing(
        chat_id,
        label[:60],
        duration,
        requester_name(callback.from_user),
        "queue" in message_text.lower(),
        thumb=result.get("poster") or result.get("thumbnail") or "",
        edit_msg=status,
    )
    await clear_loading_sticker(chat_id)


@client.on_callback_query(filters.regex(r"^mvpage\|"))
@handle_error
async def page_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    page = int(callback.data.split("|")[1])
    cached = movie_cache.get(callback.message.chat.id)
    if not cached:
        return await callback.answer("Expired")
    data = cached["data"]
    cached["page"] = page
    result = data["results"][0]
    await callback.message.edit_text(
        f"🎬 {clean_name(result.get('title', 'Movie'))} · Page {page + 1}\n\n"
        f"Choose an episode below.",
        reply_markup=build_movie_keyboard(data, page),
        parse_mode=None,
    )
    await callback.answer()


@client.on_callback_query(filters.regex(r"^adpage\|"))
@handle_error
async def adult_page_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    page = int(callback.data.split("|")[1])
    cached = adult_cache.get(callback.message.chat.id)
    if not cached:
        return await callback.answer("Expired")
    items = cached["items"]
    cached["page"] = page
    await callback.message.edit_text(
        f"🔞 Page {page + 1} · {len(items)} results\n\n" f"Choose a result below.",
        reply_markup=build_adult_keyboard(items, page),
        parse_mode=None,
    )
    await callback.answer()


@client.on_callback_query(filters.regex(r"^mv\|"))
@handle_error
async def movie_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    parts = callback.data.split("|")
    if len(parts) < 6:
        return await callback.answer("Invalid")
    _, mid, season, episode, short_lang, quality = parts
    await callback.answer("Downloading...")
    chat_id = callback.message.chat.id
    cached = movie_cache.get(chat_id)
    if not cached:
        return await callback.message.edit_text("❌ Search expired.", parse_mode=None)
    data = cached["data"]
    download_url = None
    title = "Unknown"
    thumb = ""
    for res in data.get("results", []):
        title = res.get("title", "Unknown")
        thumb = res.get("poster") or res.get("thumbnail") or res.get("image") or ""
        for ep in res.get("episodes", []):
            if str(ep.get("episode")) == str(episode) and str(
                ep.get("season", 1)
            ) == str(season):
                for q in ep.get("qualities", []):
                    if q.get("quality") == quality:
                        download_url = q.get("download_url") or q.get("downloadUrl")
                        break
                if download_url:
                    break
        if download_url:
            break
    if not download_url:
        return await callback.message.edit_text("❌ Link not found.", parse_mode=None)
    req = requester_name(callback.from_user)
    status = await callback.message.edit_text(
        status_downloading(f"{title} S{season}E{episode}", quality),
        parse_mode=None,
    )
    await start_loading_sticker(chat_id)
    filename = f"{title.replace(' ', '_')}_s{season}e{episode}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)
    if not local_path:
        await clear_loading_sticker(chat_id)
        return await status.edit_text(f"❌ Download failed\n{info}", parse_mode=None)
    success, msg = await play_local_file(
        chat_id, local_path, f"{title} S{season}E{episode}"
    )
    if not success:
        await clear_loading_sticker(chat_id)
        return await status.edit_text(f"❌ {msg}", parse_mode=None)
    dur = await duration_from_file(local_path)
    await send_now_playing(
        chat_id,
        f"{title} S{season}E{episode}",
        dur,
        req,
        "queue" in msg.lower(),
        thumb=thumb,
        edit_msg=status,
    )
    await clear_loading_sticker(chat_id)


@client.on_callback_query(filters.regex(r"^ad\|"))
@handle_error
async def adult_callback(_, callback: CallbackQuery):
    if not can_use(callback.from_user.id if callback.from_user else 0):
        return await callback.answer("Private mode", show_alert=True)
    parts = callback.data.split("|")
    if len(parts) < 3:
        return await callback.answer("Invalid")
    idx = int(parts[2])
    chat_id = callback.message.chat.id
    cached = adult_cache.get(chat_id)
    if not cached or idx >= len(cached["items"]):
        return await callback.answer("Expired")
    item = cached["items"][idx]
    title = item.get("title", "Video")
    quality = item.get("quality", "?")
    download_url = item.get("downloadUrl") or item.get("download_url")
    thumb = item.get("thumbnail") or item.get("thumb") or item.get("image") or ""
    if not download_url:
        return await callback.message.edit_text("❌ No download link.", parse_mode=None)
    await callback.answer("Downloading...")
    req = requester_name(callback.from_user)
    status = await callback.message.edit_text(
        status_downloading(title, quality),
        parse_mode=None,
    )
    await start_loading_sticker(chat_id)
    filename = f"adult_{idx}_{quality}.mp4"
    local_path, info = await download_file(download_url, filename)
    if not local_path:
        await clear_loading_sticker(chat_id)
        return await status.edit_text(f"❌ Download failed\n{info}", parse_mode=None)
    success, msg = await play_local_file(chat_id, local_path, title[:40])
    if not success:
        await clear_loading_sticker(chat_id)
        return await status.edit_text(f"❌ {msg}", parse_mode=None)
    dur = duration_from_item(item) or await duration_from_file(local_path)
    await send_now_playing(
        chat_id,
        title[:50],
        dur,
        req,
        "queue" in msg.lower(),
        thumb=thumb,
        edit_msg=status,
    )
    await clear_loading_sticker(chat_id)


print("Bot loaded: pause/seek fixed (FFGAMING)")
if __name__ == "__main__":
    client.run()
