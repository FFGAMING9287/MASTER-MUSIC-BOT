"""
Colored inline keyboards via Bot API 9.4+ style field.
Pyrogram may ignore style; we send/edit markup through raw HTTP.
"""

import aiohttp
from config import config


def player_keyboard_api(paused=False, autoplay=False):
    """Yoru-style colored controls for reply_markup JSON."""
    ap = "ON" if autoplay else "OFF"
    return {
        "inline_keyboard": [
            [
                {"text": "▶", "callback_data": "ctl|resume", "style": "success"},
                {"text": "Ⅱ", "callback_data": "ctl|pause", "style": "primary"},
                {"text": "↻", "callback_data": "ctl|replay", "style": "primary"},
                {"text": "⏭", "callback_data": "ctl|skip", "style": "primary"},
                {"text": "⏹", "callback_data": "ctl|stop", "style": "danger"},
            ],
            [
                {
                    "text": f"🔍 AUTOPLAY : {ap}",
                    "callback_data": "ctl|autoplay",
                    "style": "danger" if not autoplay else "success",
                }
            ],
            [
                {"text": "« 10s", "callback_data": "ctl|seekback", "style": "danger"},
                {"text": "10s »", "callback_data": "ctl|seekfwd", "style": "danger"},
            ],
            [
                {"text": "🎵 Close", "callback_data": "ctl|close", "style": "danger"},
            ],
        ]
    }


async def send_message_styled(chat_id, text, reply_markup=None, parse_mode="Markdown"):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return data.get("result")
                print(f"sendMessage styled fail: {data}")
                return None
    except Exception as e:
        print(f"sendMessage styled error: {e}")
        return None


async def edit_message_styled(chat_id, message_id, text=None, reply_markup=None, parse_mode="Markdown"):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            if text is not None:
                url = f"https://api.telegram.org/bot{token}/editMessageText"
                payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": parse_mode,
                }
                if reply_markup is not None:
                    payload["reply_markup"] = reply_markup
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return True
                    if "message is not modified" in str(data).lower():
                        return True
                    print(f"editMessageText fail: {data}")
                    return False
            elif reply_markup is not None:
                url = f"https://api.telegram.org/bot{token}/editMessageReplyMarkup"
                payload = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": reply_markup,
                }
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
                    if data.get("ok") or "message is not modified" in str(data).lower():
                        return True
                    print(f"editMessageReplyMarkup fail: {data}")
                    return False
    except Exception as e:
        print(f"edit styled error: {e}")
        return False
