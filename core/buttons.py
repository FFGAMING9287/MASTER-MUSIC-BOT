"""
Colored inline keyboards via Bot API style field.
Progress bar = full-width primary button (outside message text) like NOÉ.
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
    bar = "-" * filled + "♪" + "-" * max(0, width - filled - 1)
    return f"{_fmt(pos)}  {bar}  {_fmt(total)}"


def player_keyboard_api(paused=False, autoplay=False, duration=0, pos=0):
    """Controls + progress row as blue button (NOÉ style, outside text)."""
    ap = "ON" if autoplay else "OFF"
    prog = progress_button_text(duration, pos)
    return {
        "inline_keyboard": [
            # Progress OUTSIDE text body — full-width blue bar
            [
                {
                    "text": prog,
                    "callback_data": "ctl|noop",
                    "style": "primary",
                }
            ],
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
        "disable_web_page_preview": True,
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
                    "disable_web_page_preview": True,
                }
                if reply_markup is not None:
                    payload["reply_markup"] = reply_markup
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return True
                    # message not modified is ok
                    desc = str((data.get("description") or "")).lower()
                    if "not modified" in desc:
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
                    if data.get("ok"):
                        return True
                    desc = str((data.get("description") or "")).lower()
                    if "not modified" in desc:
                        return True
                    print(f"editMessageReplyMarkup fail: {data}")
                    return False
            return False
    except Exception as e:
        print(f"edit_message_styled error: {e}")
        return False
