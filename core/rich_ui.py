"""
Pure Rich Message UI — slideshows + in-message buttons (Bot API 10.1–10.3)
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
    bar = "█" * filled + "●" + "░" * max(0, width - filled)
    return f"{fmt_duration(pos)}  {bar}  {fmt_duration(total)}"


def _kb_to_api(keyboard):
    if not keyboard:
        return None
    rows = []
    for row in keyboard.inline_keyboard:
        r = []
        for btn in row:
            item = {"text": btn.text}
            if getattr(btn, "callback_data", None):
                item["callback_data"] = btn.callback_data
            if getattr(btn, "url", None):
                item["url"] = btn.url
            style = getattr(btn, "style", None)
            if style:
                item["style"] = style
            r.append(item)
        rows.append(r)
    return {"inline_keyboard": rows}


async def send_rich(chat_id, html: str, reply_markup=None):
    token = getattr(config, "BOT_TOKEN", "") or ""
    if not token:
        return False
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
                print(f"sendRichMessage fail: {data}")
                return False
    except Exception as e:
        print(f"sendRichMessage error: {e}")
        return False


# ---------- HTML cards with slideshow + in-message buttons ----------

def html_start(name: str, mode: str) -> str:
    return f"""
<h2>🎧 FFGAMING X MUSIC BOT</h2>
<p>👋 Hello <b>{name}</b>!</p>
<p>🔐 Mode : <code>{mode}</code></p>
<hr/>
<p>🎵 <b>Music</b> — <code>/song</code> <code>/yt</code></p>
<p>🎬 <b>Movies</b> — <code>/play</code> <code>/movie</code></p>
<p>🔞 <b>Adult</b> — <code>/adult</code> <code>/xxx</code></p>
<p>⏯ <b>Controls</b> — <code>/skip</code> <code>/pause</code> <code>/resume</code> <code>/stop</code> <code>/queue</code></p>
<p>🔐 <b>Owner</b> — <code>/mode public</code> | <code>private</code></p>
<hr/>
<blockquote>😌 Sit back, relax &amp; enjoy the music</blockquote>
<tg-button-row>
  <tg-button type="callback_data" data="help|song" style="primary">🎵 Song</tg-button>
  <tg-button type="callback_data" data="help|movie" style="success">🎬 Movie</tg-button>
  <tg-button type="callback_data" data="help|adult" style="danger">🔞 Adult</tg-button>
</tg-button-row>
<tg-button-row>
  <tg-button type="callback_data" data="help|ctrl">⏯ Controls</tg-button>
  <tg-button type="callback_data" data="help|full">📖 Help</tg-button>
</tg-button-row>
""".strip()


def html_help(mode: str) -> str:
    return f"""
<h2>📖 Command Guide</h2>
<p>Mode : <code>{mode}</code></p>
<hr/>
<p>🎵 <b>YouTube</b> — <code>/song</code> <code>/yt</code></p>
<p>🎬 <b>Movies</b> — <code>/play</code> <code>/movie</code></p>
<p>🔞 <b>Adult</b> — <code>/adult</code> <code>/xxx</code></p>
<p>⏯ <b>Controls</b> — <code>/skip</code> <code>/pause</code> <code>/resume</code> <code>/stop</code> <code>/queue</code></p>
<p>🔐 <b>Owner</b> — <code>/mode public|private</code></p>
<tg-button-row>
  <tg-button type="callback_data" data="help|song" style="primary">🎵 Song</tg-button>
  <tg-button type="callback_data" data="help|movie" style="success">🎬 Movie</tg-button>
  <tg-button type="callback_data" data="help|adult" style="danger">🔞 Adult</tg-button>
</tg-button-row>
""".strip()


def html_now_playing(title, duration=0, requester="User", queued=False, thumb="", pos=0) -> str:
    title = clean_name(title)[:70]
    requester = clean_name(requester)
    dur = fmt_duration(duration)
    bar = progress_bar(duration, pos)

    media = ""
    if thumb and str(thumb).startswith("http"):
        media = f"""
<tg-slideshow>
  <img src="{thumb}"/>
  <figcaption>{title}</figcaption>
</tg-slideshow>
""".strip()

    if queued:
        return f"""
<h3>🎧 Added To Queue</h3>
{media}
<p>🎵 <b>Track :</b> {title}<br/>
⏱ <b>Duration :</b> <code>{dur} MIN</code><br/>
👤 <b>Requested By :</b> {requester}</p>
""".strip()

    return f"""
<h3>🎧 Music Is Playing</h3>
{media}
<p>🎵 <b>Now Playing :</b> {title}<br/>
⏱ <b>Track Duration :</b> <code>{dur} MIN</code><br/>
👤 <b>Requested By :</b> {requester}</p>
<blockquote><code>{bar}</code></blockquote>
<p>🎶 Your track is now playing<br/>
😌 Sit back, relax &amp; enjoy the music</p>
<tg-button-row>
  <tg-button type="callback_data" data="ctl|replay" style="primary">↻ Replay</tg-button>
  <tg-button type="callback_data" data="ctl|pause" style="success">Ⅱ Pause</tg-button>
  <tg-button type="callback_data" data="ctl|skip">≫ Skip</tg-button>
</tg-button-row>
<tg-button-row>
  <tg-button type="callback_data" data="ctl|queue">☰ Queue</tg-button>
  <tg-button type="callback_data" data="ctl|stop" style="danger">⏹ Stop</tg-button>
</tg-button-row>
""".strip()


def html_search(kind: str, query: str = "", count: int = 0) -> str:
    icons = {"YouTube": "🎵", "Adult": "🔞", "Movie": "🎬", "generic": "🔍"}
    icon = icons.get(kind, "🔍")
    if count:
        return f"""
<h3>{icon} {kind} Results</h3>
<p>🔎 Query : <code>{clean_name(query)}</code><br/>
📊 Found : <b>{count}</b></p>
<blockquote>👇 Choose one from the buttons below</blockquote>
""".strip()
    return f"""
<h3>{icon} Searching {kind}...</h3>
<p>⏳ Please wait a moment</p>
""".strip()


def html_download(title: str, quality: str = "") -> str:
    q = f"<br/>📦 Quality : <code>{quality}</code>" if quality else ""
    return f"""
<h3>⬇️ Downloading</h3>
<p><code>{clean_name(title)[:55]}</code>{q}</p>
<blockquote>⏳ This may take a while...</blockquote>
""".strip()


def html_queue(body: str) -> str:
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    return f"""
<h3>☰ Queue</h3>
<p>{safe}</p>
""".strip()


def html_ping() -> str:
    return """
<h3>🤖 Pong!</h3>
<p>✅ Bot is online<br/>
🎧 Ready for Voice Chat</p>
""".strip()


def html_mode(status: str, detail: str = "") -> str:
    return f"""
<h3>🔐 Mode</h3>
<p>Status : <code>{status}</code></p>
<p>{detail}</p>
""".strip()


def html_error(msg: str) -> str:
    return f"""
<h3>❌ Error</h3>
<p>{clean_name(msg)[:200]}</p>
""".strip()


def html_info(title: str, body: str) -> str:
    return f"""
<h3>{title}</h3>
<p>{body}</p>
""".strip()


def plain_now_playing(title, duration=0, requester="User", queued=False, queue_len=0, pos=0):
    title = clean_name(title)[:55]
    requester = clean_name(requester)
    dur = fmt_duration(duration)
    if queued:
        return (
            f"🎧 **Added To Queue**\n\n"
            f"🎵 **Track :** {title}\n"
            f"⏱ **Duration :** `{dur} MIN`\n"
            f"👤 **By :** {requester}"
        )
    bar = progress_bar(duration, pos)
    return (
        f"🎧 **Music Is Playing**\n\n"
        f"🎵 **Now Playing :** {title}\n"
        f"⏱ **Duration :** `{dur} MIN`\n"
        f"👤 **Requested By :** {requester}\n\n"
        f"`{bar}`\n\n"
        f"🎶 Your track is now playing\n"
        f"😌 Sit back, relax & enjoy"
    )


def status_searching(kind="YouTube"):
    return f"🔍 **Searching {kind}...**\n\n⏳ Please wait"


def status_downloading(title, quality=""):
    q = f"\n📦 `{quality}`" if quality else ""
    return f"⬇️ **Downloading**\n\n`{clean_name(title)[:50]}`{q}\n\n⏳ Please wait"


def status_results(kind, query, count):
    return f"{kind} **Results**\n\n🔎 `{query}`\n📊 **{count}** found\n\n👇 Choose"
