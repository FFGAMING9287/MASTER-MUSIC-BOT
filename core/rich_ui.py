"""
Telegram Rich Messages (Bot API 10.1+) for Now Playing card.
Falls back to plain text if sendRichMessage is unsupported.
"""

import aiohttp
from config import config


def fmt_duration(sec):
    if not sec:
        return "--:--"
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def build_now_playing_html(title: str, duration=0, requester: str = "User", queued: bool = False, thumb: str = ""):
    dur = fmt_duration(duration)
    safe_title = (title or "Unknown").replace("<", "").replace(">", "")[:80]
    safe_req = (requester or "User").replace("<", "").replace(">", "")[:60]

    if queued:
        header = "🎧 Added To Queue"
        body = f"🎵 <b>Track :</b> {safe_title}\n⏱ <b>Duration :</b> <code>{dur}</code>\n👤 <b>Requested By :</b> {safe_req}"
    else:
        header = "🎧 Music Is Playing"
        body = (
            f"🎵 <b>Now Playing :</b> {safe_title}\n"
            f"⏱ <b>Track Duration :</b> <code>{dur}</code>\n"
            f"👤 <b>Requested By :</b> {safe_req}\n\n"
            f"🎶 Your track is now playing\n"
            f"😌 Sit back, relax &amp; enjoy the music"
        )

    media = ""
    if thumb and thumb.startswith("http"):
        media = f'<tg-slideshow><img src="{thumb}"/><figcaption>{safe_title}</figcaption></tg-slideshow>\n\n'

    # In-message buttons (Bot API 10.3) — no Clone
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

    html = f"<h3>{header}</h3>\n{media}<p>{body}</p>\n{buttons}"
    return html


def plain_now_playing(title, duration=0, requester="User", queued=False):
    dur = fmt_duration(duration)
    if queued:
        return (
            f"🎧 **Added To Queue**\n\n"
            f"🎵 **Track :** {title}\n"
            f"⏱ **Duration :** `{dur}`\n"
            f"👤 **Requested By :** {requester}\n"
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
    """Try Bot API sendRichMessage; return True if sent."""
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return False

    html = build_now_playing_html(title, duration, requester, queued, thumb)
    url = f"https://api.telegram.org/bot{token}/sendRichMessage"
    payload = {
        "chat_id": chat_id,
        "rich_message": {"html": html},
    }
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
