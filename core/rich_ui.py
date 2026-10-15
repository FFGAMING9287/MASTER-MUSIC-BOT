"""
Now Playing card — progress bar helpers + photo/rich send
"""

import re
import aiohttp
from config import config


def fmt_duration(sec):
    if not sec:
        return "00:00"
    try:
        sec = int(sec)
    except Exception:
        return "00:00"
    m, s = divmod(max(0, sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def clean_name(text: str) -> str:
    if not text:
        return "User"
    text = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.strip()
    return text[:60] if text else "User"


def progress_bar(duration: int, pos: int = 0) -> str:
    total = max(int(duration or 0), 1)
    pos = max(0, min(int(pos or 0), total))
    width = 14
    filled = int((pos / total) * width)
    bar = "━" * filled + "●" + "─" * max(0, width - filled)
    return f"`{fmt_duration(pos)}  {bar}  {fmt_duration(total)}`"


def plain_now_playing(title, duration=0, requester="User", queued=False, queue_len=0, pos=0):
    title = clean_name(title)[:55]
    requester = clean_name(requester)
    dur = fmt_duration(duration)

    if queued:
        return (
            f"🎧 **ADDED TO QUEUE**\n\n"
            f"🎵 **TRACK :** {title}\n"
            f"⏱ **DURATION :** `{dur} MIN`\n"
            f"👤 **REQUESTED BY :** {requester}"
        )

    bar = progress_bar(duration, pos)
    return (
        f"🎧 **MUSIC IS PLAYING**\n\n"
        f"🎵 **NOW PLAYING :** {title}\n"
        f"⏱ **TRACK DURATION :** `{dur} MIN`\n"
        f"👤 **REQUESTED BY :** {requester}\n\n"
        f"{bar}\n\n"
        f"🎶 Your track is now playing\n"
        f"😌 Sit back, relax & enjoy the music"
    )


def build_now_playing_html(title, duration=0, requester="User", queued=False, thumb="", pos=0):
    dur = fmt_duration(duration)
    safe_title = clean_name(title)[:80]
    safe_req = clean_name(requester)
    bar = progress_bar(duration, pos).replace("`", "")

    if queued:
        header = "🎧 Added To Queue"
        body = (
            f"🎵 <b>Track :</b> {safe_title}<br/>"
            f"⏱ <b>Duration :</b> <code>{dur} MIN</code><br/>"
            f"👤 <b>Requested By :</b> {safe_req}"
        )
    else:
        header = "🎧 Music Is Playing"
        body = (
            f"🎵 <b>Now Playing :</b> {safe_title}<br/>"
            f"⏱ <b>Track Duration :</b> <code>{dur} MIN</code><br/>"
            f"👤 <b>Requested By :</b> {safe_req}<br/><br/>"
            f"<code>{bar}</code><br/><br/>"
            f"🎶 Your track is now playing<br/>"
            f"😌 Sit back, relax &amp; enjoy the music"
        )

    media = ""
    if thumb and str(thumb).startswith("http"):
        media = f'<tg-slideshow><img src="{thumb}"/><figcaption>{safe_title}</figcaption></tg-slideshow><br/>'

    return f"<h3>{header}</h3>{media}<p>{body}</p>"


def _kb_to_api(keyboard):
    if not keyboard:
        return None
    rows = []
    for row in keyboard.inline_keyboard:
        r = []
        for btn in row:
            item = {"text": btn.text}
            if btn.callback_data:
                item["callback_data"] = btn.callback_data
            if btn.url:
                item["url"] = btn.url
            r.append(item)
        rows.append(r)
    return {"inline_keyboard": rows}


async def send_rich_now_playing(chat_id, title, duration=0, requester="User", queued=False, thumb="", reply_markup=None):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return False

    html = build_now_playing_html(title, duration, requester, queued, thumb)
    url = f"https://api.telegram.org/bot{token}/sendRichMessage"
    payload = {"chat_id": chat_id, "rich_message": {"html": html}}
    api_kb = _kb_to_api(reply_markup)
    if api_kb:
        payload["reply_markup"] = api_kb

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return True
                return False
    except Exception as e:
        print(f"sendRichMessage error: {e}")
        return False


async def send_photo_now_playing(chat_id, title, duration=0, requester="User", queued=False, thumb="", reply_markup=None):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token or not thumb or not str(thumb).startswith("http"):
        return False

    caption = plain_now_playing(title, duration, requester, queued)
    if len(caption) > 1000:
        caption = caption[:997] + "..."

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": thumb,
        "caption": caption,
        "parse_mode": "Markdown",
    }
    api_kb = _kb_to_api(reply_markup)
    if api_kb:
        payload["reply_markup"] = api_kb

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    # return message id for progress tracking
                    return data.get("result", {}).get("message_id") or True
                return False
    except Exception as e:
        print(f"sendPhoto error: {e}")
        return False
