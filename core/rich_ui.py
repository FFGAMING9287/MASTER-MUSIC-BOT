"""
Rich Message UI — Felix-style table lines + in-message buttons
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


# ---------- Felix-style cards with table lines ----------

def html_start(name: str, mode: str) -> str:
    return f"""
<h2>🎧 FFGAMING X MUSIC BOT</h2>
<p>Welcome to <b>FFGAMING X MUSIC</b>, {name} ✨</p>
<hr/>
<p>📋 <b>Bot Information</b></p>
<table>
<tr><td>Mode</td><td>{mode}</td></tr>
<tr><td>Status</td><td>Online ✅</td></tr>
<tr><td>Voice Chat</td><td>Supported</td></tr>
</table>
<hr/>
<p>🎵 <b>Features</b></p>
<table>
<tr><td>Music</td><td><code>/song</code> <code>/yt</code></td></tr>
<tr><td>Movies</td><td><code>/play</code> <code>/movie</code></td></tr>
<tr><td>Adult</td><td><code>/adult</code> <code>/xxx</code></td></tr>
<tr><td>Controls</td><td><code>/skip</code> <code>/pause</code> <code>/stop</code></td></tr>
<tr><td>Owner</td><td><code>/mode public|private</code></td></tr>
</table>
<hr/>
<blockquote>😌 Sit back, relax &amp; enjoy the music</blockquote>
<p>↑ Select a menu below to continue</p>
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
<p>📋 <b>All Commands</b></p>
<table>
<tr><td>🎵 YouTube</td><td><code>/song</code> <code>/yt</code></td></tr>
<tr><td>🎬 Movies</td><td><code>/play</code> <code>/movie</code></td></tr>
<tr><td>🔞 Adult</td><td><code>/adult</code> <code>/xxx</code></td></tr>
<tr><td>⏯ Controls</td><td><code>/skip</code> <code>/pause</code> <code>/resume</code></td></tr>
<tr><td></td><td><code>/stop</code> <code>/queue</code></td></tr>
<tr><td>🔐 Owner</td><td><code>/mode public|private</code></td></tr>
</table>
<hr/>
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
<hr/>
<table>
<tr><td>Track</td><td>{title}</td></tr>
<tr><td>Duration</td><td><code>{dur} MIN</code></td></tr>
<tr><td>Requested By</td><td>{requester}</td></tr>
</table>
""".strip()

    return f"""
<h3>🎧 Music Is Playing</h3>
{media}
<hr/>
<table>
<tr><td>Now Playing</td><td>{title}</td></tr>
<tr><td>Duration</td><td><code>{dur} MIN</code></td></tr>
<tr><td>Requested By</td><td>{requester}</td></tr>
</table>
<hr/>
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
<hr/>
<table>
<tr><td>Query</td><td><code>{clean_name(query)}</code></td></tr>
<tr><td>Found</td><td><b>{count}</b></td></tr>
</table>
<hr/>
<blockquote>👇 Choose one from the buttons below</blockquote>
""".strip()
    return f"""
<h3>{icon} Searching {kind}...</h3>
<p>⏳ Please wait a moment</p>
""".strip()


def html_download(title: str, quality: str = "") -> str:
    qrow = f"<tr><td>Quality</td><td><code>{quality}</code></td></tr>" if quality else ""
    return f"""
<h3>⬇️ Downloading</h3>
<hr/>
<table>
<tr><td>Title</td><td>{clean_name(title)[:55]}</td></tr>
{qrow}
</table>
<hr/>
<blockquote>⏳ This may take a while...</blockquote>
""".strip()


def html_queue(body: str) -> str:
    safe = body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    return f"""
<h3>☰ Queue</h3>
<hr/>
<p>{safe}</p>
""".strip()


def html_ping() -> str:
    return """
<h3>🤖 Pong!</h3>
<hr/>
<table>
<tr><td>Status</td><td>Online ✅</td></tr>
<tr><td>Voice Chat</td><td>Ready</td></tr>
</table>
""".strip()


def html_mode(status: str, detail: str = "") -> str:
    return f"""
<h3>🔐 Mode</h3>
<hr/>
<table>
<tr><td>Status</td><td><code>{status}</code></td></tr>
</table>
<p>{detail}</p>
""".strip()


def html_error(msg: str) -> str:
    return f"""
<h3>❌ Error</h3>
<hr/>
<p>{clean_name(msg)[:200]}</p>
""".strip()


def html_info(title: str, body: str) -> str:
    return f"""
<h3>{title}</h3>
<hr/>
<p>{body}</p>
""".strip()


def plain_now_playing(title, duration=0, requester="User", queued=False, queue_len=0, pos=0):
    title = clean_name(title)[:55]
    requester = clean_name(requester)
    dur = fmt_duration(duration)
    if queued:
        return (
            f"🎧 **Added To Queue**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎵 Track : `{title}`\n"
            f"⏱ Duration : `{dur} MIN`\n"
            f"👤 By : {requester}\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    bar = progress_bar(duration, pos)
    return (
        f"🎧 **Music Is Playing**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎵 Now Playing : `{title}`\n"
        f"⏱ Duration : `{dur} MIN`\n"
        f"👤 Requested By : {requester}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
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
    return (
        f"{kind} **Results**\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔎 Query : `{query}`\n"
        f"📊 Found : **{count}**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👇 Choose"
    )
