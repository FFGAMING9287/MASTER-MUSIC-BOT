"""
Telegram Rich Messages + plain fallback for Now Playing card.
"""

import re
import aiohttp
from config import config


def fmt_duration(sec):
    if not sec:
        return "--:--"
    try:
        sec = int(sec)
    except Exception:
        return "--:--"
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def clean_name(text: str) -> str:
    """Strip HTML / mention markup to plain name."""
    if not text:
        return "User"
    # Remove <a href=...>Name</a>
    text = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.strip()
    return text[:50] if text else "User"


def build_now_playing_html(title: str, duration=0, requester: str = "User", queued: bool = False, thumb: str = ""):
    dur = fmt_duration(duration)
    safe_title = clean_name(title)[:80]
    safe_req = clean_name(requester)

    if queued:
        header = "🎧 Added To Queue"
        body = (
            f"🎵 <b>Track :</b> {safe_title}<br/>"
            f"⏱ <b>Duration :</b> <code>{dur}</code><br/>"
            f"👤 <b>Requested By :</b> {safe_req}"
        )
    else:
        header = "🎧 Music Is Playing"
        body = (
            f"🎵 <b>Now Playing :</b> {safe_title}<br/>"
            f"⏱ <b>Track Duration :</b> <code>{dur}</code><br/>"
            f"👤 <b>Requested By :</b> {safe_req}<br/><br/>"
            f"🎶 Your track is now playing<br/>"
            f"😌 Sit back, relax &amp; enjoy the music"
        )

    media = ""
    if thumb and str(thumb).startswith("http"):
        media = f'<tg-slideshow><img src="{thumb}"/><figcaption>{safe_title}</figcaption></tg-slideshow><br/>'

    buttons = """
<tg-button-row>
  <tg-button type="callback_data" data="ctl|replay" style="primary">↻ Replay</tg-button>
  <tg-button type="callback_data" data="ctl|pause" style="success">Ⅱ Pause</tg-button>
  <tg-button type="callback_data" data="ctl|skip">≫ Skip</tg-button>
</tg-button-row>
<tg-button-row>
  <tg-button type="callback_data" data="ctl|queue">☰ Queue</tg-button>
  <tg-button type="callback_data" data="ctl|stop" style="danger">⏹ Stop</tg-button>
</tg-button-row>
"""
    return f"<h3>{header}</h3>{media}<p>{body}</p>{buttons}"


def plain_now_playing(title, duration=0, requester="User", queued=False):
    dur = fmt_duration(duration)
    title = clean_name(title)
    requester = clean_name(requester)
    if queued:
        return (
            f"🎧 **Added To Queue**\n\n"
            f"🎵 **Track :** {title}\n"
            f"⏱ **Duration :** `{dur}`\n"
            f"👤 **Requested By :** {requester}"
        )
    return (
        f"🎧 **Music Is Playing**\n\n"
        f"🎵 **Now Playing :** {title}\n"
        f"⏱ **Track Duration :** `{dur}`\n"
        f"👤 **Requested By :** {requester}\n\n"
        f"🎶 Your track is now playing\n"
        f"😌 Sit back, relax & enjoy the music"
    )


async def send_rich_now_playing(chat_id, title, duration=0, requester="User", queued=False, thumb=""):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return False

    html = build_now_playing_html(title, duration, requester, queued, thumb)
    url = f"https://api.telegram.org/bot{token}/sendRichMessage"
    payload = {"chat_id": chat_id, "rich_message": {"html": html}}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    print("Rich message sent OK")
                    return True
                print(f"sendRichMessage failed: {data}")
                return False
    except Exception as e:
        print(f"sendRichMessage error: {e}")
        return False
