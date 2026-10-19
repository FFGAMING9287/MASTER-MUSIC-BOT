"""
Telegram UI helpers for the music player.

Player progress is rendered as a full-width button beneath an artwork card.
"""

import aiohttp

from config import config


def _fmt(sec):
    try:
        sec = int(sec or 0)
    except Exception:
        sec = 0
    m, s = divmod(max(0, sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def progress_button_text(duration=0, pos=0):
    total = max(int(duration or 0), 1)
    pos = max(0, min(int(pos or 0), total))
    width = 14
    filled = int((pos / total) * width) if total else 0
    filled = min(max(filled, 0), width - 1)
    bar = "━" * filled + "●" + "━" * max(0, width - filled - 1)
    return f"{_fmt(pos)}  {bar}  {_fmt(total)}"


def player_keyboard_api(paused=False, autoplay=False, duration=0, pos=0, queue_len=0):
    """Build the now-playing controls and progress row."""
    ap = "ON" if autoplay else "OFF"
    pause_text = "▶ Resume" if paused else "Ⅱ Pause"
    pause_action = "ctl|resume" if paused else "ctl|pause"
    return {
        "inline_keyboard": [
            [
                {
                    "text": progress_button_text(duration, pos),
                    "callback_data": "ctl|noop",
                    "style": "primary",
                }
            ],
            [
                {"text": "↻ Replay", "callback_data": "ctl|replay", "style": "primary"},
                {
                    "text": pause_text,
                    "callback_data": pause_action,
                    "style": "success" if paused else "primary",
                },
                {"text": "⏭ Skip", "callback_data": "ctl|skip", "style": "primary"},
            ],
            [
                {
                    "text": f"☰ Queue · {queue_len}",
                    "callback_data": "ctl|queue",
                    "style": "success",
                },
                {"text": "⏹ End Queue", "callback_data": "ctl|stop", "style": "danger"},
            ],
            [
                {
                    "text": f"Autoplay: {ap}",
                    "callback_data": "ctl|autoplay",
                    "style": "success" if autoplay else "danger",
                }
            ],
        ]
    }


def queue_keyboard_api():
    """Controls shown on an item that has been added to the queue."""
    return {
        "inline_keyboard": [
            [
                {
                    "text": "▶ Play Now",
                    "callback_data": "ctl|playnow",
                    "style": "success",
                },
                {"text": "⏭ Skip", "callback_data": "ctl|skip", "style": "primary"},
            ],
            [{"text": "⏹ End Queue", "callback_data": "ctl|stop", "style": "danger"}],
        ]
    }


async def _api_call(method, payload):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data.get("result") or True
                description = data.get("description") or data
                if "not modified" in str(description).lower():
                    return True
                print(f"{method} fail: {description}")
    except Exception as exc:
        print(f"{method} error: {exc}")
    return None


async def send_message_styled(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _api_call("sendMessage", payload)


async def send_photo_styled(
    chat_id, photo, caption, reply_markup=None, parse_mode="HTML"
):
    payload = {
        "chat_id": chat_id,
        "photo": photo,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _api_call("sendPhoto", payload)


async def edit_message_media_styled(
    chat_id, message_id, photo, caption, reply_markup=None, parse_mode="HTML"
):
    media = {
        "type": "photo",
        "media": photo,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    payload = {"chat_id": chat_id, "message_id": message_id, "media": media}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return await _api_call("editMessageMedia", payload)


async def edit_message_styled(
    chat_id, message_id, text=None, reply_markup=None, parse_mode="HTML", media=False
):
    payload = {"chat_id": chat_id, "message_id": message_id}
    if text is not None:
        method = "editMessageCaption" if media else "editMessageText"
        payload["caption" if media else "text"] = text
        payload["parse_mode"] = parse_mode
        if not media:
            payload["disable_web_page_preview"] = True
    elif reply_markup is not None:
        method = "editMessageReplyMarkup"
    else:
        return False
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return bool(await _api_call(method, payload))
